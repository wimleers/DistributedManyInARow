import copy
import Queue
import uuid
from optparse import OptionParser
import unittest


from GlobalState import *
from Service import OneToManyService




class GlobalStateTest(unittest.TestCase):

    def testReceiving(self):
        sessionUUID = str(uuid.uuid1())
        senderUUID = str(uuid.uuid1())
        otherSenderUUID = str(uuid.uuid1())

        service = OneToManyService('testhost', 'testService', 1600)
        service.registerDestination(senderUUID)

        gs = GlobalState(service, sessionUUID, senderUUID)
        gs.start()

        v1 = VectorClock()
        v2 = VectorClock()

        # Fake the sending of a message. (uncomment this and the test will pass for some reason)
        v1.increment(senderUUID)
        messageOne = {sessionUUID : {'message' : 'join', 'senderUUID' : senderUUID, 'originUUID' : senderUUID, 'clock' : v1}}
        with gs.lock:
           gs.outbox.put(messageOne)

        # Fake the receiving of a message.
        v2.increment(senderUUID)
        v2.increment(otherSenderUUID)
        messageTwo = {sessionUUID : {'message' : 'test', 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
        with service.lock:
            service.inbox[senderUUID].put(messageTwo)

         # Allow the thread to run.
        time.sleep(0.2)

        count = 0
        with gs.lock:
            while gs.inbox.qsize() > 0:
                message = gs.inbox.get()
                count = count+1

        #make sure the received message has the correct values
        self.assertEquals (count, 1)
        self.assertEquals (message['message'], 'test')
        self.assertEquals (message['senderUUID'], otherSenderUUID)
        self.assertEquals (message['originUUID'], otherSenderUUID)
        self.assertEquals (message['clock'], v2)


    def testMultipleReceiving(self):
        sessionUUID = str(uuid.uuid1())
        senderUUID = str(uuid.uuid1())
        otherSenderUUID = str(uuid.uuid1())
        service = OneToManyService('testhost', 'testService', 1600)
        service.registerDestination(senderUUID)

        gs = GlobalState(service, sessionUUID, senderUUID)
        gs.start()

        v1 = VectorClock()
        v2 = VectorClock()

        # Fake the receiving of three messages in the wrong order.
        v2 = copy.deepcopy(v2)
        v2.increment(otherSenderUUID)
        messageOne = {sessionUUID : {'message' : '1', 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
        v2 = copy.deepcopy(v2)
        v2.increment(otherSenderUUID)
        messageTwo = {sessionUUID : {'message' : "2", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
        v2 = copy.deepcopy(v2)
        v2.increment(otherSenderUUID)
        messageThree = {sessionUUID : {'message' : "3", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
        with service.lock:
            service.inbox[senderUUID].put(messageTwo)
            service.inbox[senderUUID].put(messageThree)
            service.inbox[senderUUID].put(messageOne)

         # Allow the thread to run.
        time.sleep(0.2)

        #add all the messages in an array
        messages = []
        with gs.lock:
            while gs.inbox.qsize() > 0:
                messages.append(gs.inbox.get())

        #make sure we have the correct number of messages, and that they arrived in the correct order
        self.assertEquals (len(messages), 3)
        self.assertEquals (messages[0]['message'], '1')
        self.assertEquals (messages[1]['message'], '2')
        self.assertEquals (messages[2]['message'], '3')


    def testLostMessage(self):
        sessionUUID = str(uuid.uuid1())
        senderUUID = str(uuid.uuid1())
        otherSenderUUID = str(uuid.uuid1())
        service = OneToManyService('testhost', 'testService', 1600)
        service.registerDestination(senderUUID)

        gs = GlobalState(service, sessionUUID, senderUUID)
        gs.start()

        v1 = VectorClock()
        v2 = VectorClock()

         # Fake the loss of a message
        v2 = copy.deepcopy(v2)
        v2.increment(otherSenderUUID)
        v2.increment(otherSenderUUID)
        messageSix = {sessionUUID : {'message' : "This should never show up in the inbox because a message was lost.", 'senderUUID' : otherSenderUUID, 'originUUID' : otherSenderUUID, 'clock' : v2}}
        with service.lock:
            service.inbox[senderUUID].put(messageSix)

        time.sleep(0.2)

        count = 0
        with gs.lock:
            while gs.inbox.qsize() > 0:
                message = gs.inbox.get()
                count = count + 1

        self.assertEquals(count, 0)




if __name__ == "__main__":
    unittest.main()
