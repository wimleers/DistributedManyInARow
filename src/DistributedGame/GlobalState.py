# General imports.
import cPickle
import shutil
import sqlite3
import time

# Imports from this module.
import VectorClock


class HistoryError(Exception): pass
class ClockError(HistoryError): pass
class MessageError(HistoryError): pass


# TODO: originUUID (for original sender) alongside senderUUID?


class GlobalState(object):
    """A global state contains the history of all messages sent for a
    distributed application, persistently stored. This is not a "dumb" global
    state, but a "smart" one: when the global state is inconsistent (due to
    undelivered messages), it will stop passing through messages to the code
    that interacts with GlobalState until the global state is consistent once
    again.
    Peers may rejoin within a certain timeframe after being disconnected and
    will be able to continue as if nothing had happened.
    Assumptions: each sender has a UUID, a VectorClock is used for
    synchronization and SQLite is used for persistent storage.
    """

    def __init__(self, UUID, dbFile="./history.sqlite", peerWaitingTime=30, messageWaitingTime=2):
        # Set up the SQLite database for persistent storage.
        sqlite3.register_converter("pickle", cPickle.loads)
        sqlite3.register_converter("VectorClock", VectorClock.loads)
        self._dbFile = dbFile
        self._dbCon = sqlite3.connect(self._dbFile, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self._dbCur = self.dbCon.cursor()
        self._prepareDB()

        # Own data.
        self.UUID = UUID

        # Settings.
        self._peerWaitingTime    = int(peerWaitingTime)
        self._messageWaitingTime = int(messageWaitingTime)

        # Other things.
        self.lock = threading.Lock() # Must be acquired before accessing the DB.
        self._startedWaitingForMessages = None
        self.clock = None


    def __del__(self):
        os.remove(self._dbFile)


    def export(self, filename):
        """Export this global state (i.e. an SQLite database) to a file."""

        with self.lock:
            shutil.copy(self._dbFile, filename)


    def _prepareDB(self):
        """Prepare the database (create the table structure)."""

        with self.lock:
            self._dbCur.execute("CREATE TABLE IF NOT EXISTS history(hid INTEGER PRIMARY KEY AUTOINCREMENT, timestamp float, senderUUID text, clock VectorClock, message pickle)")
            # TODO: add index on clock, if it makes a difference
            self._dbCon.commit()


    def frontier(self):
        """Get the current frontier (which is the frontier of a consistent
        cut), because the global state always contains a consistent cut
        (otherwise it's queued).
        """
        return self.clock.dict()


    def messageByVectoryClock(self, clock):
        """Get the message associated with a specific vector clock."""

        hid, senderUUID, message = self.dbCur.execute("SELECT hid, senderUUID, message FROM history WHERE vectorClock = ?", (clock.dumps(), )).fetchone()
        return hid, senderUUID, message


    def messageByHistoryID(self, hid):
        """Get the message associated with a history ID."""

        clock, senderUUID, message = self.dbCur.execute("SELECT clock, senderUUID, message FROM history WHERE hid = ?", (hid, )).fetchone()
        return clock, senderUUID, message


    def messages(self, minHid, maxHid):
        """Get a list of messages, starting with minHid and ending with maxHid
        (i.e. including minHid and including maxHid).
        """

        grids = {}
        self.dbCur.execute("SELECT hid, senderUUID FROM grids WHERE groupName = ?", (group, ))
        resultList = self.dbCur.fetchall()
        for id, name in resultList:
            grids[id] = name
        return grids


    def sendMessage(self, message):
        """Send a message and store it in the global state.
        
        Returns the resulting hid (history ID).
        """

        # Increment the vector clock for our message.
        self.clock.increment(self.UUID)

        # Store the message.
        self.dbCur.execute("INSERT INTO history (timestamp, senderUUID, clock, message) VALUES(?, ?, ?, ?)", (time.time(), senderUUID, clock.dumps(), cPickle.dumps(message)))
        self.dbCon.commit()
        hid = self.dbCur.lastrowid

        # Actually send the message.
        # TODO
        #outbox.add(clock, message)

        return hid


    def receiveMessage(self, senderUUID, remoteClock, message):
        """Store a message and its associated vector clock and sender UUID.

        Returns the resulting hid (history ID).
        """

        # If the 'happened before' relationship is no longer intact, take
        # appropriate measures.
        if not self.clock <= remoteClock:
            if not self.clock.isConcurrentWith(remoteClock):
                self.clock.getSmallerComponents(remoteClock)
                raise ClockError

        # Merge the clocks and increment our own component.
        self.clock.merge(remoteClock)
        remoteClock = self.clock

        # Store the message.
        self.dbCur.execute("INSERT INTO history (timestamp, senderUUID, clock, message) VALUES(?, ?, ?, ?)", (time.time(), senderUUID, clock.dumps(), cPickle.dumps(message)))
        self.dbCon.commit()
        hid = self.dbCur.lastrowid

        # Perform a callback?
        # TODO

        return hid


    def erase(self):
        self.dbCur.execute("DROP TABLE history")
        self.dbCon.commit()


    def run(self):
        while True:
            # sending can happen immediately (delayed incoming messages will be considered concurrent)
            # TODO: send queue -> send!
            
            # If there are incoming messages, attempt to process them.
            with self.lock:
                if len(inbox) > 0:
                    # Sort the clocks, so the lowest one comes first.
                    sortedClocks = sorted(inbox.keys())
                    # If the lowest clock (i.e. the first clock of the sorted
                    # clocks) is <= or || with the current clock, then we can
                    # process it.
                    # However, <= or || are not sufficient. We add the
                    # constraint of a maximum difference of 1. This is
                    # necessary to detect messages lost in transmission.
                    lowestClock = sortedClocks[0]
                    # if self.clock <= lowestClock or self.clock.isConcurrentWith(lowestClock):
                    if self.clock.isImmediatelyFollowedBy(lowestClock) or self.clock.isImmediatelyConcurrentWith(lowestClock):
                        self.receiveMessage(inbox[lowestClock]) # TODO details
                        self.clock.merge(lowestClock)
                    # If the lowest clock didn't qualify for these conditions,
                    # then none of the clocks of the messages in th inbox are.
                    # So it's time to check if a message was lost in
                    # transmission. But give the system messageWaitingTime
                    # time to still receive delayed messages.
                    else:
                        currentTime = time.time()
                        if self._startedWaitingForMessages is None:
                            self._startedWaitingForMessages = currentTime
                        elif currentTime > self._startedWaitingForMessages + _messageWaitingTime:
                            ids = self.clock.getSmallerComponents(lowestClock, 2):
                            # TODO: ask for a resend
                        # TODO: handle crashed processes

