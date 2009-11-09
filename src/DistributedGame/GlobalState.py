# General imports.
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


class GlobalStateError(Exception): pass
class ClockError(GlobalStateError): pass
class MessageError(GlobalStateError): pass
class MulticastMessagingClassError(GlobalStateError): pass


# TODO: support to detect crashed processes (send a message every peerWaitingTime time and require answer within peerWaitingTime, if not: process crashed)
# TODO: support to request lost messages (if missing message still not arrived after messageWaitingTime, send this request)
# TODO: add index on clock, if it makes a difference


MessageRecord = namedtuple('Message', ['hid', 'timestamp', 'senderUUID', 'originUUID', 'ownClockValue', 'clock', 'message'])


class GlobalState(threading.Thread):
    """A global state contains the history of all messages sent for a
    distributed application, persistently stored. This is not a "dumb" global
    state, but a "smart" one: when the global state is inconsistent (due to
    undelivered messages), it will stop passing through messages to the code
    that interacts with GlobalState until the global state is consistent once
    again.
    Peers may rejoin within a certain timeframe after being disconnected and
    will be able to continue as if nothing had happened.
    Can use any multicast technology, as long as it has an input queue, an
    output queue and a lock, accepts messages as dicts (with keys being
    headers and values being contents) and serializes variables automatically.
    Get from the inbox, put into the outbox.
    Assumptions: the session in which senders participate has a UUID, each
    sender has a UUID, a VectorClock is used for synchronization and SQLite is
    used for persistent storage.
    """

    def __init__(self, sessionUUID, senderUUID, multicast, dbFile="./globalstate.sqlite", peerWaitingTime=30, messageWaitingTime=2):
        # MulticastMessaging subclass.
        if not isinstance(multicast, MulticastMessaging):
            raise MulticastMessagingClassError
        self.multicast = multicast

        # Identifiers.
        self.sessionUUID = sessionUUID
        self.senderUUID  = senderUUID

        # Message storage.
        self.inbox       = Queue.Queue()
        self.outbox      = Queue.Queue()
        self.waitingRoom = {} # Waiting room: received messages that still need to be processed.

        # Settings.
        self.peerWaitingTime    = int(peerWaitingTime)
        self.messageWaitingTime = int(messageWaitingTime)

        # State variables.
        self.alive = True
        self.die = False

        # Other things.
        self.lock = threading.Condition()
        self._startedWaitingForMessages = None
        self.clock = VectorClock()
        self.clock.add(self.senderUUID)

        # SQLite database. Actual setup happens when the thread is up and
        # running: SQLite objects are thread-bound.
        self._dbFile = dbFile
        self._dbCon = None
        self._dbCur = None

        super(GlobalState, self).__init__()



    ##########################################################################
    # Persistent storage.                                                    #
    ##########################################################################

    def __del__(self):
        if os.path.exists(self._dbFile):
            os.remove(self._dbFile)


    def export(self, filename):
        """Export this global state (i.e. an SQLite database) to a file."""

        with self.lock:
            shutil.copy(self._dbFile, filename)


    def _prepareDB(self):
        """Prepare the database (create the table structure)."""

        with self.lock:
            sqlite3.register_converter("pickle", cPickle.loads)
            sqlite3.register_converter("VectorClock", VectorClock.loads)
            self._dbCon = sqlite3.connect(self._dbFile, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
            self._dbCur = self._dbCon.cursor()
            self._dbCur.execute("CREATE TABLE IF NOT EXISTS MessageHistory(\
                                    hid           INTEGER PRIMARY KEY AUTOINCREMENT, \
                                    timestamp     float NOT NULL, \
                                    senderUUID    text NOT NULL, \
                                    originUUID    text NOT NULL, \
                                    ownClockValue INTEGER DEFAULT NULL, \
                                    clock         VectorClock NOT NULL, \
                                    message       pickle NOT NULL)")
            self._dbCon.commit()


    def frontier(self):
        """Get the current frontier (which is the frontier of a consistent
        cut), because the global state always contains a consistent cut
        (otherwise it's queued).
        """
        return self.clock.dict()


    def messageByVectoryClock(self, clock):
        """Get the message associated with a specific vector clock."""

        self._dbCur.execute("SELECT * FROM MessageHistory WHERE vectorClock = ?", (clock.dumps(), ))
        message = map(MessageRecord._make, self._dbCur.fetchone())
        return message


    def messageByHistoryID(self, hid):
        """Get the message associated with a MessageHistory ID."""

        self._dbCur.execute("SELECT * FROM MessageHistory WHERE hid = ?", (hid, ))
        message = map(MessageRecord._make, self._dbCur.fetchone())
        return message


    def ownMessages(self, minClockValue, maxClockValue):
        """Get a list of messages sent by us, starting with the clock value
        minClockValuem and ending with the clock value maxClockValue (i.e.
        including minClockValue and including maxClockValue).
        """

        messages = {}
        self._dbCur.execute("SELECT * FROM MessageHistory WHERE senderUUID = ? AND ownClockValue > ? AND ownClockValue < ?", (self.UUID, minClockValue, maxClockValue))
        for message in map(MessageRecord._make, self._dbCur.fetchall()):
            messages[message.ownClockValue] = message
        return messages


    ##########################################################################
    # Message processing.                                                    #
    ##########################################################################

    def sendMessage(self, message):
        """Enqueue a message to be sent."""
        with self.lock:
            self.outbox.put(message)


    def receiveMessage(self):
        """Receive all messages waiting in the inbox."""
        with self.lock:
            while self.inbox.qsize() > 0:
                yield self.inbox.get()


    def _sendMessage(self, message):
        """Store a message in the global state and actually send it by passing
        it on to the multicast outbox.
        """

        # Increment the vector clock for our message.
        self.clock.increment(self.senderUUID)

        # Add the clock to the message.
        message['clock'] = self.clock

        # Store the message.
        self._dbCur.execute("INSERT INTO MessageHistory (timestamp, senderUUID, originUUID, clock, ownClockValue, message) VALUES(?, ?, ?, ?, ?, ?)", (time.time(), self.senderUUID, self.senderUUID, self.clock.dumps(), self.clock[self.senderUUID], cPickle.dumps(message)))
        self._dbCon.commit()

        # Use the passed in multicast implementation to send the message.
        with self.multicast.lock:
            self.multicast.outbox.put(message)
            self.multicast.lock.notifyAll()


    def _receiveMessage(self, message):
        """Store a message in the global state and put it in the inbox."""

        # Merge the clocks and increment our own component.
        self.clock.merge(message['clock'])
        message['clock'] = self.clock

        # Store the message.
        self._dbCur.execute("INSERT INTO MessageHistory (timestamp, senderUUID, originUUID, clock, message) VALUES(?, ?, ?, ?, ?)", (time.time(), message['senderUUID'], message['originUUID'], self.clock.dumps(), cPickle.dumps(message)))
        self._dbCon.commit()

        # Move the message to the inbox queue, so it can be retrieved.
        with self.lock:
            self.inbox.put(message)


    def erase(self):
        """Erase the global state."""
        self._dbCur.execute("DROP TABLE MessageHistory")
        self._dbCon.commit()
        self.clock = VectorClock()
        self.clock.add(self.UUID)


    def run(self):
        self._prepareDB()

        while self.alive:
            # Check if it's time to send liveness messages.
            # TODO

            # Retrieve incoming messages and store them in the waiting room.
            with self.lock:
                with self.multicast.lock:
                    while self.multicast.inbox.qsize() > 0:
                        message = self.multicast.inbox.get()
                        # Check if the message has a header that is addressed
                        # to the session we're participating in.
                        if message.has_key(self.sessionUUID): # TODO: this obviously fails when another thread/module wants to retrieves messages from the queue, so we need to add a router in between
                            content = message[self.sessionUUID]
                            clock = content['clock']
                            self.waitingRoom[clock] = content
                            print "moved message to waiting room with clock", clock

            # Sending can always happen immediately. The application that uses
            # this module only sends messages if they either don't require
            # mutual exclusion (i.e. order of events is unimportant) or when
            # it has acquired the lock for mutual exclusion.
            with self.lock:
                while self.outbox.qsize() > 0:
                    message = self.outbox.get()
                    self._sendMessage(message)
                    print "sent message with clock", message['clock']

            # If there are incoming messages, attempt to process them. Delayed
            # messages will be waited for, lost messages will be re-requested.
            with self.lock:
                processedMessage = True
                while processedMessage and len(self.waitingRoom) > 0:
                    # Sort the clocks of the messages in the waiting, so the
                    # lowest one comes first.
                    sortedClocks = sorted(self.waitingRoom.keys(), VectorClock.sort)
                    # print "sorted clocks", sortedClocks

                    # If the lowest clock (i.e. the first clock of the sorted
                    # clocks) is "immediately followed" (<= with a difference
                    # of 1) or "immediately concurrent" (|| with a difference
                    # of 2 ids with one +1 and the other one -1), then we can
                    # process it. This is necessary to guarantee correct order.
                    lowestClock = sortedClocks[0]
                    if self.clock.isImmediatelyFollowedBy(lowestClock) or self.clock.isImmediatelyConcurrentWith(lowestClock):
                        self._receiveMessage(self.waitingRoom[lowestClock])
                        del self.waitingRoom[lowestClock]
                        print "moved message from waiting room to inbox, clock:", lowestClock

                    # If the lowest clock didn't qualify to be processed, then
                    # none of the clocks of the messages in the inbox are.
                    # So it's time to check if a message was lost in
                    # transmission. But give the system messageWaitingTime
                    # time to still receive the delayed message(s).
                    else:
                        # Stop processing incoming messages, because we must
                        # wait for a missing message to arrive.
                        processedMessage = False
                    #     currentTime = time.time()
                    #     if self._startedWaitingForMessages is None:
                    #         self._startedWaitingForMessages = currentTime
                    #     elif currentTime > self._startedWaitingForMessages + self.messageWaitingTime:
                    #         ids = self.clock.getSmallerComponents(lowestClock, 2):
                    #         # TODO: ask for a resend
                    #     # TODO: handle crashed processes

                # Notify threads waiting to receive incoming messages that new
                # messages are available.
                self.lock.notifyAll()

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)


    def kill(self):
        # Let the thread know it should commit suicide.
        with self.lock:
            self.die = True


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Stop us from running any further.
        self.alive = False




if __name__ == "__main__":
    import copy
    import uuid
    from MulticastMessaging import MulticastMessaging
    from optparse import OptionParser

    sessionUUID = str(uuid.uuid1())
    senderUUID = str(uuid.uuid1())
    otherSenderUUID = str(uuid.uuid1())
    multicast = MulticastMessaging()

    gs = GlobalState(sessionUUID, senderUUID, multicast)
    gs.start()

    v1 = VectorClock()
    v2 = VectorClock()

    # Fake the sending of a message.
    v1.increment(senderUUID)
    messageOne = {sessionUUID : {'message' : 'join', 'senderUUID' : senderUUID, 'originUUID' : senderUUID, 'clock' : v1}}
    with gs.lock:
        gs.outbox.put(messageOne)

    # Fake the receiving of a message.
    v2.increment(senderUUID)
    v2.increment(otherSenderUUID)
    messageTwo = {sessionUUID : {'message' : 'welcome', 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
    with multicast.lock:
        multicast.inbox.put(messageTwo)

    # Fake the receiving of two message in the wrong order.
    v2 = copy.deepcopy(v2)
    v2.increment(otherSenderUUID)
    messageThree = {sessionUUID : {'message' : 'Knock knock!', 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
    v2 = copy.deepcopy(v2)
    v2.increment(otherSenderUUID)
    messageFour = {sessionUUID : {'message' : "Who's there?", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
    v2 = copy.deepcopy(v2)
    v2.increment(otherSenderUUID)
    messageFive = {sessionUUID : {'message' : "This joke is so old!", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
    with multicast.lock:
        multicast.inbox.put(messageFour)
        multicast.inbox.put(messageFive)
        multicast.inbox.put(messageThree)

    # Fake the loss of a message
    v2 = copy.deepcopy(v2)
    v2.increment(otherSenderUUID)
    v2.increment(otherSenderUUID)
    messageSix = {sessionUUID : {'message' : "This should never show up in the inbox because a message was lost.", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
    with multicast.lock:
        multicast.inbox.put(messageSix)

    # Allow the thread to run.
    time.sleep(1)

    # Now print the contents of the messages in the (hopefully) ordered inbox.
    with gs.lock:
        while gs.inbox.qsize() > 0:
            message = gs.inbox.get()
            print message

    gs.kill()
