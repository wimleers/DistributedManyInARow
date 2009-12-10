# General imports.
import copy
import cPickle
import os
import Queue
import shutil
import sqlite3
import threading
import time
from collections import namedtuple as namedtuple
import ntplib

# Imports from this module.
from VectorClock import VectorClock
import Service


class GlobalStateError(Exception): pass
class ClockError(GlobalStateError): pass
class MessageError(GlobalStateError): pass
class OneToManyServiceError(GlobalStateError): pass


# TODO: support to detect crashed processes (send a message every peerWaitingTime time and require answer within peerWaitingTime, if not: process crashed)
# TODO: support to request lost messages (if missing message still not arrived after messageWaitingTime, send this request)
# TODO: add index on clock, if it makes a difference




class MessageProcessor(threading.Thread):
    """The message processor processes all incoming messages, and handles all 
        election and host-related messages. It also handles checking of hosts/players
        leaving
    """
    
    KEEP_ALIVE_TYPE = 'KEEP-ALIVE'
    SERVER_MOVE_TYPE = 'SERVER-MESSAGE'
    SERVER_ELECTED_TYPE = 'SERVER-ELECTED'
    
    def __init__(self, service, sessionUUID, senderUUID, peerWaitingTime=30, messageWaitingTime=2):
        # MulticastMessaging subclass.
        if not isinstance(service, Service.OneToManyService):
            raise OneToManyServiceError
        self.service = service

        # Identifiers.
        self.sessionUUID = sessionUUID
        self.senderUUID  = senderUUID
        self.players = 1
        
        #The last time the keep-alive message was sent (in seconds)
        #self.keepAliveSentTime = 0
        #The time to wait between keep-alive messages
        #self.keepAliveTreshold = 1
        #self.keepAliveLeftTime = 5 #the time to wait for a keep-alive message to arrive before we disconnect the player 
        #self.keepAliveMessages = {} # Contains the last time a keep-alive message was received per player

        # Message storage.
        self.inbox       = Queue.Queue()
        self.outbox      = Queue.Queue()

        # Settings.
        self.peerWaitingTime    = int(peerWaitingTime)
        self.messageWaitingTime = int(messageWaitingTime)

        # Thread state variables.
        self.alive = True
        self.die = False
        self.lock = threading.Condition()
        
        #Keep-alive.
        self.playerRTT = {}
        self.playerRTT['max'] = -1
        self.lastKeepAliveSendTime = time.time()
        self.keepAliveSent = False
        self.receivedAliveMessages = {}
        
        # election based variables
        # the time at which a new host was selected. If we get any new elected messages, we can ignore them
        # if they happened before this time
        self.hostElectedTime = 0

        # Other things.
        self._startedWaitingForMessages = None
        self.NTPoffset = 0

        # Register this Global State's session UUID with the service as a
        # valid destination.
        self.service.registerDestination(self.sessionUUID)

        super(MessageProcessor, self).__init__()



    ##########################################################################
    # Message processing.                                                    #
    ##########################################################################

    def sendMessage(self, message, sendToSelf = True):
        """Enqueue a message to be sent."""
        with self.lock:
            # print "\tGlobalState.sendMessage()", message
            envelope = self._wrapMessage(message)
            if sendToSelf:
                self.inbox.put((self.senderUUID, message))
            with self.service.lock:
                # print "\tGlobalState._sendMessage()", envelope
                self.service.sendMessage(self.sessionUUID, envelope)
                self.service.lock.notifyAll()

    def countReceivedMessages(self):
        with self.lock:
            return self.inbox.qsize()


    def receiveMessage(self):
        with self.lock:
            return self.inbox.get()

    def sendKeepAliveMessage(self):
        with self.service.lock:
            self.sendMessage({'type' : self.KEEP_ALIVE_TYPE, 'originUUID':self.senderUUID, 'timestamp' : time.time() + self.NTPoffset}, False)
            
    def receiveKeepAliveMessage(self, message):
        print 'received keep_alive'
        with self.lock:
            uuid = message['originUUID']
            timeDiff = (time.time() + self.NTPoffset) - message['timestamp']
            rtt = 2 * timeDiff
            
            self.receivedAliveMessages[uuid] = message['timestamp']
            
            
            
            if not uuid in self.playerRTT.keys():
                self.playerRTT[uuid] = rtt
            else:
                self.playerRTT[uuid] = (self.playerRTT[uuid] + rtt) / 2
            
            max = 0
            self.playerRTT['max'] = 0
            for key in self.playerRTT.keys():
                if (key != 'max' and key != 'avg'):    
                    if rtt > max:
                        max = rtt
            if max > self.playerRTT['max']:
                self.playerRTT['max'] = max
            
            if not 'avg' in self.playerRTT.keys():
                self.playerRTT['avg'] = rtt
            else:
                self.playerRTT['avg'] = 0
                avg = 0
                count = 0
                for key in self.playerRTT.keys():
                    if (key != 'max' and key != 'avg'):       
                        avg += self.playerRTT[key]
                        count += 1
                avg = avg / count
                self.playerRTT['avg'] = avg
            

    #checks if any players disconnected
    def checkKeepAlive(self):
        print 'checking keep-alive'
        with self.lock:
            for key in self.receivedAliveMessages.keys():
                print str(30 * self.playerRTT['max'] + self.receivedAliveMessages[key])
                print str(time.time() + self.NTPoffset)
                if  30 * self.playerRTT['max'] + self.receivedAliveMessages[key] < time.time() + self.NTPoffset:
                    
                    del self.receivedAliveMessages[key]
                    del self.playerRTT[key]
                    
                    if key == self.host:
                        if len(self.receivedAliveMessages) < 1 or self.senderUUID > max (self.receivedAliveMessages.keys()):
                            print 'sending elected message'
                            electedMessage = {'type' : self.SERVER_ELECTED_TYPE, 'host' : self.senderUUID, 'timestamp' : time.time() + self.NTPoffset}
                            self.sendMessage(electedMessage)
                            self.receiveElectedMessage({'message':electedMessage})
                    self.hostLeftAt = time.time() + self.NTPoffset
                    self.inbox.put((key, {'type':4}))
                    
                    
    def receiveElectedMessage(self, envelope):
        if envelope['message']['timestamp'] > self.hostElectedTime:
            self.hostElectedTime = envelope['message']['timestamp']
            self.host = envelope['message']['host']
                  
    def receiveLeaveMessage(self, envelope):
        self.receivedAliveMessages[envelope['originUUID']] = 0
        self.checkKeepAlive()
    
    def _wrapMessage(self, message):
        """Wrap a message in an envelope to prepare it for sending."""

        envelope = {}
        # Add the timestamp to the envelope.
        envelope['timestamp'] = time.time() + self.NTPoffset
        # Add the sender UUUID and the original sender UUID to the envelope
        # (which is always ourselves).
        envelope['senderUUID'] = envelope['originUUID'] = self.senderUUID
        # Store the message in the envelope.
        envelope['message'] = message
        return envelope


    def processMessage(self, envelope):
        """Process a message and put it in the inbox if its meant for us"""

        # Merge the clocks and increment our own component.
        if envelope['message']['type'] == self.SERVER_MOVE_TYPE:
            if envelope['message']['target'] == self.senderUUID:
                with self.lock:
                    self.inbox.put((envelope['originUUID'], envelope['message']))
        elif envelope['message']['type'] == self.KEEP_ALIVE_TYPE:
            self.receiveKeepAliveMessage(envelope)
        elif envelope['message']['type'] == self.SERVER_ELECTED_TYPE:
            self.receiveElectedMessage(envelope)
        #if the message is a LEAVE message
        elif envelope['message']['type'] == 4:
            self.receiveLeaveMessage(envelope)
        else:    
            # Move the message to the inbox queue, so it can be retrieved.
            with self.lock:
                self.inbox.put((envelope['originUUID'], envelope['message']))


    def erase(self):
        """Erase the global state."""
        # Remove this Global State's session UUID as a valid destination.
        self.service.removeDestination(self.sessionUUID)
        # Reset the database.
        self._dbCur.execute("DELETE FROM MessageHistory")
        self._dbCon.commit()
        self.clock = VectorClock()
        self.clock.add(self.senderUUID)
        
    def getNTPoffset(self):
        # get the NTP offset of this computers clock
        try:
            client = ntplib.NTPClient()
            response = client.request('europe.pool.ntp.org', version=3)
            if response.leap != 3:
                self.NTPoffset = response.offset
        except:
            print 'Warning! NTP server could not be reached'
            pass
            
        # print 'NTPoffset is now: ' + str(self.NTPoffset)

    def run(self):
        self.getNTPoffset()

        while self.alive:
            # Check if it's time to send liveness messages.
            # TODO

            # Retrieve incoming messages and store them in the waiting room.            
            with self.lock:
                with self.service.lock:
                    if self.service.countReceivedMessages(self.sessionUUID) > 0:
                        envelope = self.service.receiveMessage(self.sessionUUID)
                        # Ignore our own messages.
                        
                        if envelope['senderUUID'] != self.senderUUID:
                            self.processMessage(envelope)
                    
                    if('avg' in self.playerRTT.keys()):
                        print self.playerRTT['avg']
                        if(float(self.playerRTT['avg']) < 0.2 * float(time.time() - self.lastKeepAliveSendTime)):
                            print 'sending keepAlive'
                            self.sendKeepAliveMessage()
                            self.checkKeepAlive()
                            self.lastKeepAliveSendTime = time.time()
                    elif self.players != 1 and not self.keepAliveSent:
                        self.keepAliveSent = True
                        self.sendKeepAliveMessage()
                        self.lastKeepAliveSendTime = time.time()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)


    def kill(self):
        # Let the thread know it should commit suicide. But first let it send
        # all remaining messages.
        # while self.outbox.qsize() > 0:
        #     if 
        with self.lock:
            self.die = True


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Stop us from running any further.
        self.alive = False
