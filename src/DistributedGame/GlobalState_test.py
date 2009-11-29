import copy
import Queue
import uuid
from optparse import OptionParser
import unittest


from GlobalState import *
from Service import OneToManyService
from Player import Player




class GlobalStateTest(unittest.TestCase):

    def setUp(self):
        # Initialize OneToManyService.
        self.service_a = OneToManyService('testhost', '_testService._tcp', 1600)
        self.service_a.start()

        # Generate a game UUID.
        self.gameUUID = str(uuid.uuid1())

        # Generate a Player: we will use its UUID.
        self.player_a = Player('A')

        # Initialize the GlobalState.
        self.gs_a = GlobalState(self.service_a, self.gameUUID, self.player_a.UUID)
        self.gs_a.start()

        # Now start generating all of the above for the second game.
        self.service_b = OneToManyService('testhost', '_testService._tcp', 1600)
        self.service_b.start()
        self.player_b = Player('B')
        self.gs_b = GlobalState(self.service_b, self.gameUUID, self.player_b.UUID)
        self.gs_b.start()

        # Create two vector clocks that we'll increment as we send messages.
        # We'll use these for validation later on.
        self.clock_a = VectorClock()
        self.clock_a.add(self.player_a.UUID)
        self.clock_b = VectorClock()
        self.clock_b.add(self.player_b.UUID)


    def tearDown(self):
        self.service_a.kill()
        self.service_b.kill()
        self.gs_a.kill()
        self.gs_b.kill()


    def assertInSync(self, clock_a, clock_b, inSync=True):
        # Ensure both Global States' frontiers are correct and in sync.
        self.assertEquals(self.gs_a.frontier(), clock_a.dict())
        self.assertEquals(self.gs_b.frontier(), clock_b.dict())
        if inSync:
            self.assertTrue(clock_a == clock_b)
        else:
            self.assertFalse(clock_a == clock_b)


    def testSingleMessage(self):
        # Player A sends message.
        messageOne = {'type' : 'join'}
        self.gs_a.sendMessage(messageOne)
        self.clock_a.increment(self.player_a.UUID)
        self.clock_b.increment(self.player_a.UUID)

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.gs_a.countReceivedMessages(), 0)
        self.assertEquals(self.gs_b.countReceivedMessages(), 1)
        self.assertEquals(self.gs_b.receiveMessage(), (self.player_a.UUID, messageOne))

        # Ensure both Global States are in sync.
        self.assertInSync(self.clock_a, self.clock_b)


    def testMultipleMessages(self):
        # Player A sends message.
        messageOne = {'type' : 'join'}
        self.gs_a.sendMessage(messageOne)
        self.clock_a.increment(self.player_a.UUID)
        self.clock_b.increment(self.player_a.UUID)

        # Player B sends message.
        messageTwo = {'type' : 'welcome'}
        self.gs_b.sendMessage(messageTwo)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.gs_a.countReceivedMessages(), 1)
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageTwo))
        self.assertEquals(self.gs_b.countReceivedMessages(), 1)
        self.assertEquals(self.gs_b.receiveMessage(), (self.player_a.UUID, messageOne))

        # Ensure both Global States are in sync.
        self.assertInSync(self.clock_a, self.clock_b)


    def testMultipleOutOfOrderMessages(self):
        # Player A sends message (but not really).
        messageOne = {'type' : 'join'}
        envelopeOne = self.gs_a._wrapMessage(messageOne)
        self.clock_a.increment(self.player_a.UUID)
        self.clock_b.increment(self.player_a.UUID)

        # Player B sends many message (but not really).
        messageTwo = {'type' : 'welcome'}
        envelopeTwo = self.gs_b._wrapMessage(messageTwo)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageThree = {'type' : '1'}
        envelopeThree = self.gs_b._wrapMessage(messageThree)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageFour = {'type' : '2'}
        envelopeFour = self.gs_b._wrapMessage(messageFour)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageFive = {'type' : '3'}
        envelopeFive = self.gs_b._wrapMessage(messageFive)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)

        # Send the messages severely out of order.
        self.service_b.sendMessage(self.gameUUID, envelopeThree)
        self.service_a.sendMessage(self.gameUUID, envelopeOne)
        self.service_b.sendMessage(self.gameUUID, envelopeFive)
        self.service_b.sendMessage(self.gameUUID, envelopeTwo)
        self.service_b.sendMessage(self.gameUUID, envelopeFour)

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.gs_a.countReceivedMessages(), 4)
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageTwo))
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageThree))
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageFour))
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageFive))
        self.assertEquals(self.gs_b.countReceivedMessages(), 1)
        self.assertEquals(self.gs_b.receiveMessage(), (self.player_a.UUID, messageOne))

        # Ensure both Global States are in sync.
        self.assertInSync(self.clock_a, self.clock_b)


    def testLostMessage(self):
        # Player A sends message (but not really).
        messageOne = {'type' : 'join'}
        envelopeOne = self.gs_a._wrapMessage(messageOne)
        self.clock_a.increment(self.player_a.UUID)
        self.clock_b.increment(self.player_a.UUID)

        # Player B sends many message (but not really).
        messageTwo = {'type' : 'welcome'}
        envelopeTwo = self.gs_b._wrapMessage(messageTwo)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageThree = {'type' : '1'}
        envelopeThree = self.gs_b._wrapMessage(messageThree)
        self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageFour = {'type' : '2'}
        envelopeFour = self.gs_b._wrapMessage(messageFour)
        # Don't increment the reference clock for player A, because we will
        # fake the loss of message four.
        # self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)
        messageFive = {'type' : '3'}
        envelopeFive = self.gs_b._wrapMessage(messageFive)
        # Don't increment the reference clock for player A, because we will
        # fake the loss of message four, which means message five also won't
        # arrive.
        # self.clock_a.increment(self.player_b.UUID)
        self.clock_b.increment(self.player_b.UUID)

        # Send the messages severely out of order.
        self.service_b.sendMessage(self.gameUUID, envelopeThree)
        self.service_a.sendMessage(self.gameUUID, envelopeOne)
        self.service_b.sendMessage(self.gameUUID, envelopeFive)
        self.service_b.sendMessage(self.gameUUID, envelopeTwo)
        # Don't send message four, which will prevent message five from
        # arriving.
        #self.service_b.sendMessage(self.gameUUID, envelopeFour)

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.gs_a.countReceivedMessages(), 2)
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageTwo))
        self.assertEquals(self.gs_a.receiveMessage(), (self.player_b.UUID, messageThree))
        self.assertEquals(self.gs_b.countReceivedMessages(), 1)
        self.assertEquals(self.gs_b.receiveMessage(), (self.player_a.UUID, messageOne))

        # Ensure both Global States are NOT in sync.
        self.assertInSync(self.clock_a, self.clock_b, False)




if __name__ == "__main__":
    unittest.main()
