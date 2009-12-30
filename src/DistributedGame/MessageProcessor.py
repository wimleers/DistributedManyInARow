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
    
    MOVE, CHAT, JOIN, WELCOME, LEAVE, FREEZE, UNFREEZE, NONE= range(8)
    HISTORY_MESSAGE_TYPE = 'HISTORY_MESSAGE'
    KEEP_ALIVE_TYPE = 'KEEP-ALIVE'
    SERVER_MOVE_TYPE = 'SERVER-MESSAGE'
    SERVER_ELECTED_TYPE = 'SERVER-ELECTED'
    SERVER_RESPONSE_TYPE = 'SERVER-RESPONSE'
    
    def __init__(self, service, sessionUUID, senderUUID, peerWaitingTime=30, messageWaitingTime=2):
        # MulticastMessaging subclass.
        if not isinstance(service, Service.OneToManyService):
            raise OneToManyServiceError
        self.service = service

        # Identifiers.
        self.sessionUUID = sessionUUID
        self.senderUUID  = senderUUID
        self.players = None
        
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
        self.sendAfterFirstKeepAlive = False
        self.receivedAliveMessages = {}
        
        # election based variables
        self.host = None
        # the time at which a new host was selected. If we get any new elected messages, we can ignore them
        # if they happened before this time
        self.hostElectedTime = 0
        # list of the moves and joins we sent out, and haven't been replied to yet
        # if we don't get a reply in 5 roundtrip times, the host has left, and the 
        # message wasn't delivered
        self.messagesAwaitingApproval = []

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
            # send a keepalive message which contains the NTP time at which it was sent, so we can calculate
            # Roundtrip time, and see if a player leaves the game
            if self.useNTP:
                self.sendMessage({'type' : self.KEEP_ALIVE_TYPE, 'originUUID':self.senderUUID, 'timestamp' : time.time() + self.NTPoffset}, False)
            else:
                self.sendMessage({'type' : self.KEEP_ALIVE_TYPE, 'originUUID':self.senderUUID, 'timestamp' : 0}, False)
            
    def receiveKeepAliveMessage(self, message):
        with self.lock:
            uuid = message['originUUID']
            #calculate the time difference between the time the message was sent and received
            timeDiff = (time.time() + self.NTPoffset) - message['timestamp']
            #calculate the roundtrip time
            rtt = 2 * timeDiff
            
            if self.useNTP and message['timestamp'] != 0:            
                self.receivedAliveMessages[uuid] = message['timestamp']
            else:
                rtt = 2
                self.receivedAliveMessages[uuid] = time.time()
            
            if not uuid in self.playerRTT.keys():
                self.playerRTT[uuid] = rtt
            else:
                # calculate the average between the previous rtt for this player, and the current one
                self.playerRTT[uuid] = (self.playerRTT[uuid] + rtt) / 2
            
            max = 0
            #calculate the maximum of all the roundtrip times
            if not 'avg' in self.playerRTT.keys():
                self.playerRTT['max'] = rtt
            else:
                for key in self.playerRTT.keys():
                    if (key != 'max' and key != 'avg'):    
                        if self.playerRTT[key] > max:
                            max = self.playerRTT[key]
                if max > self.playerRTT['max']:
                    self.playerRTT['max'] = (max + self.playerRTT['max'])/2
            
            #calculate the average roundtrip time
            if not 'avg' in self.playerRTT.keys():
                self.playerRTT['avg'] = rtt
            else:
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
        with self.lock:
            for key in self.receivedAliveMessages.keys():
                #a player has left if he hasn't send a message in 5 roundtrip times
                if  5 * self.playerRTT['max'] + self.receivedAliveMessages[key] + 1 < time.time() + self.NTPoffset:
                    
                    del self.receivedAliveMessages[key]
                    del self.playerRTT[key]
                    
                    # if the player who left was the host, we have to determine the new host
                    if self.host != None and key == self.host:
                        # this player becomes the host if he has the highest UUID of all players
                        if len(self.receivedAliveMessages) < 1 or self.senderUUID > max (self.receivedAliveMessages.keys()):
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
        players = copy.deepcopy(self.players)
        del players[envelope['originUUID']]
        
        if not self.useNTP and self.host != None and envelope['originUUID'] == self.host:
            if len(self.players) == 1 or self.senderUUID > max (players.keys()):
                electedMessage = {'type' : self.SERVER_ELECTED_TYPE, 'host' : self.senderUUID, 'timestamp' : time.time() + self.NTPoffset}
                self.sendMessage(electedMessage)
                self.receiveElectedMessage({'message':electedMessage})
        self.inbox.put((envelope['originUUID'], {'type':4}))
        # if we can't use ntp, we can't rely on the keep-alive messages
        # to pick a new host, so manually select a new host
    
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
        
    def messageApproval(self, message):
        """ Approves a message sent by this user """
        
        if message['target'] == self.senderUUID:
            # If we received a history message, it means we have correctly joined the game
            if message['type'] == self.HISTORY_MESSAGE_TYPE:
                for m in self.messagesAwaitingApproval:
                    # Remove the join message
                    if m['type'] == self.JOIN:
                        self.messagesAwaitingApproval.remove(m)
            # If we received a server response message, it means the move we sent was processed
            if message['type'] == self.SERVER_RESPONSE_TYPE:
                for m in self.messagesAwaitingApproval:
                    # Delete the move message
                    if m['type'] == self.SERVER_MOVE_TYPE and m['col'] == message['col']:
                        self.messagesAwaitingApproval.remove(m)
                        
                        
    def checkApproval(self):
        """ Check if a message sent by this user was approved and sends it again if it timed out """
        for m in self.messagesAwaitingApproval:
            # wait till a new host was elected before sending the message again
            if m['timestamp'] < self.hostElectedTime:
                # a message times out if it wasn't approved after 5 roundtrip times
                if  5 * self.playerRTT['max'] + m['timestamp'] + 1 < time.time() + self.NTPoffset:
                    # send the message again
                    self.sendMessage(m)
                    self.messagesAwaitingApproval.remove(m)
                    if self.senderUUID != self.host:
                        m['timestamp'] = time.time() + self.NTPoffset
                        self.messagesAwaitingApproval.append(m)


    def processMessage(self, envelope):
        """Process a message and put it in the inbox if its meant for us"""

        # If the message was a request to make a move, do the move, and let the player who
        # did the move know his message was processed
        if envelope['message']['type'] == self.SERVER_MOVE_TYPE:
            if envelope['message']['target'] == self.senderUUID:
                with self.lock:
                    self.sendMessage({'type' : self.SERVER_RESPONSE_TYPE, 'col' : envelope['message']['col'], 'target' : envelope['originUUID']})
                    self.inbox.put((envelope['originUUID'], envelope['message']))
        # If the message was an approval of a message sent by this user, approve that message
        elif envelope['message']['type'] == self.SERVER_RESPONSE_TYPE:
            self.messageApproval(envelope['message'])
        # Process a keep-alive message
        elif envelope['message']['type'] == self.KEEP_ALIVE_TYPE:
            self.receiveKeepAliveMessage(envelope)
        # Process an elected message
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
            self.useNTP = True
        except:
            print 'Warning! NTP server could not be reached'
            self.useNTP = False
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
                    # If there are other players, send keepalive messages with an interval suitable
                    # to their roundtrip time
                    if self.useNTP and ('avg' in self.playerRTT.keys()):
                        if(float(min(self.playerRTT['avg'], 1)) < float(time.time() - self.lastKeepAliveSendTime)):
                            self.sendKeepAliveMessage()
                            self.checkKeepAlive()
                            # check if move and join requests were received
                            self.checkApproval()
                            self.lastKeepAliveSendTime = time.time()
                    elif time.time() - self.lastKeepAliveSendTime > 1:
                        self.keepAliveSent = True
                        self.sendKeepAliveMessage()
                        self.checkKeepAlive()
                        self.checkApproval()
                        self.lastKeepAliveSendTime = time.time()

            # 100 refreshes per second is plenty.
            time.sleep(0.01)


    def kill(self):
        # Let the thread know it should commit suicide. But first let it send
        # all remaining messages.
        # while self.outbox.qsize() > 0:
        #     if 
        with self.lock:
            self._commitSuicide()


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Stop us from running any further.
        self.alive = False
