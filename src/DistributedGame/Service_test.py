import copy
import Queue
import uuid
from optparse import OptionParser
import unittest


from GlobalState import *
from Service import OneToManyService




class OneToManyServiceTest(unittest.TestCase):

    def setUp(self):
        # Initialize OneToManyService.
        self.service = OneToManyService('testhost', '_testService._tcp', 1600)
        self.service.start()


    def tearDown(self):
        self.service.kill()


    def testSimpleMessage(self):
        # Generate a session UUID and register it as a destination.
        sessionUUID = str(uuid.uuid1())
        self.service.registerDestination(sessionUUID)

        # Send message.
        self.service.sendMessage(sessionUUID, 'test')

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.service.countReceivedMessages(sessionUUID), 1)
        self.assertEquals(self.service.receiveMessage(sessionUUID), 'test')


    def testSimpleServiceMessage(self):
        # Send service message.
        self.service.sendServiceMessage('test')

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.service.countReceivedServiceMessages(), 1)
        self.assertEquals(self.service.receiveServiceMessage(), 'test')


    def testAdvancedMessaging(self):
        # Generate two session UUIDs and register them as a destinations.
        sessionUUID_a = str(uuid.uuid1())
        sessionUUID_b = str(uuid.uuid1())
        self.service.registerDestination(sessionUUID_a)
        self.service.registerDestination(sessionUUID_b)

        # Send messages.
        self.service.sendMessage(sessionUUID_a, 'test A1')
        self.service.sendMessage(sessionUUID_b, 'test B1')
        self.service.sendMessage(sessionUUID_b, 'test B2')
        self.service.sendServiceMessage('test service')

        # Alow messages to be processed.
        time.sleep(1)

        # Validate.
        self.assertEquals(self.service.countReceivedServiceMessages(), 1)
        self.assertEquals(self.service.receiveServiceMessage(), 'test service')
        self.assertEquals(self.service.countReceivedMessages(sessionUUID_a), 1)
        self.assertEquals(self.service.receiveMessage(sessionUUID_a), 'test A1')
        self.assertEquals(self.service.countReceivedMessages(sessionUUID_b), 2)
        self.assertEquals(self.service.receiveMessage(sessionUUID_b), 'test B1')        




if __name__ == "__main__":
    unittest.main()
