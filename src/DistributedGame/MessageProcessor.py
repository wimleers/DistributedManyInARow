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
    
    def __init__(self, service, sessionUUID, senderUUID, peerWaitingTime=30, messageWaitingTime=2):
        # MulticastMessaging subclass.
        if not isinstance(service, Service.OneToManyService):
            raise OneToManyServiceError
        self.service = service

        # Identifiers.
        self.sessionUUID = sessionUUID
        self.senderUUID  = senderUUID
        
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

        # Other things.
        self._startedWaitingForMessages = None
        self.clock = VectorClock()
        self.clock.add(self.senderUUID)

        # Register this Global State's session UUID with the service as a
        # valid destination.
        self.service.registerDestination(self.sessionUUID)

        super(MessageProcessor, self).__init__()



    ##########################################################################
    # Message processing.                                                    #
    ##########################################################################

    def sendMessage(self, message, sendToSelf = True):
        """Enqueue a message to be sent."""
        print sendToSelf
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
            self.service.sendServiceMessage({'type' : self.KEEP_ALIVE_TYPE, 'originUUID':self.senderUUID})
            self.keepAliveSentTime = time.clock()
            
    def receiveKeepAliveMessage(self, message):
        with self.lock:
            self.keepAliveMessages[message['originUUID']] = time.clock()
        
    #checks if any players disconnected
    def checkKeepAlive(self):
        with self.lock:
            for key in self.keepAliveMessages.keys():
                if time.clock() - self.keepAliveMessages[key] > self.keepAliveLeftTime:
                    self.inbox.put((key, {'type':4}, None))
                    del self.keepAliveMessages[key]
    
    def _wrapMessage(self, message):
        """Wrap a message in an envelope to prepare it for sending."""

        envelope = {}
        # Increment the vector clock for our envelope.
        self.clock.increment(self.senderUUID)
        # Add the clock to the envelope.
        envelope['clock'] = copy.deepcopy(self.clock)
        # Add the sender UUUID and the original sender UUID to the envelope
        # (which is always ourselves).
        envelope['senderUUID'] = envelope['originUUID'] = self.senderUUID
        # Store the message in the envelope.
        envelope['message'] = message
        return envelope


    def processMessage(self, envelope):
        """Store a message in the global state and put it in the inbox."""

        # Merge the clocks and increment our own component.
        print envelope
        if envelope['message']['type'] == self.SERVER_MOVE_TYPE:
            if envelope['message']['target'] == self.senderUUID:
                with self.lock:
                    print 'putting it in inbox'
                    self.inbox.put((envelope['originUUID'], envelope['message']))
                    
        else:    
            # Move the message to the inbox queue, so it can be retrieved.
            with self.lock:
                print 'putting it in inbox'
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


    def run(self):

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
                            # print "\tGlobalstate.run(): moved message to waiting room with clock", clock
                    if self.service.countReceivedServiceMessages() > 0:
                        envelope = self.service.receiveServiceMessage()
                        if envelope['type'] == self.KEEP_ALIVE_TYPE:
                            self.receiveKeepAliveMessage(envelope)
                        if ('originUUID' in envelope.keys()):
                            self.inbox.put((envelope['originUUID'], envelope))
                        else:
                            self.inbox.put((None, envelope))

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
