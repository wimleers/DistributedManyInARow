import Queue
import threading
import time
from IPMulticastMessaging import IPMulticastMessaging
from ZeroconfMessaging import ZeroconfMessaging


class Service(threading.Thread):


    SERVICE_TO_SERVICE = 'service-to-service'


    def __init__(self, serviceName, serviceType, port, protocolVersion=1):
        super(Service, self).__init__(name='Service-Thread')

        # Initialize IP Multicast layer.
        self.multicast = IPMulticastMessaging(port)
        uniquePort = self.multicast.getSendPort()
        self.multicast.start()

        # Initialize zeroconf layer.
        self.zeroconf = ZeroconfMessaging(serviceName, serviceType, uniquePort, protocolVersion,
                                          serviceRegisteredCallback=self._serviceRegisteredCallback,
                                          serviceRegistrationFailedCallback=self._serviceRegistrationFailedCallback,
                                          serviceUnregisteredCallback=self._serviceUnregisteredCallback,
                                          peerServiceDiscoveryCallback=self._peerServiceDiscoveryCallback,
                                          peerServiceRemovalCallback=self._peerServiceRemovalCallback,
                                          peerServiceUpdateCallback=self._peerServiceUpdateCallback,
                                          peerServiceDescriptionUpdatedCallback=self._peerServiceDescriptionUpdatedCallback)
        self.zeroconf.start()

        # Message storage.
        self.inbox  = Queue.Queue()
        self.outbox = Queue.Queue()

        # Service description storage.
        self.ownServiceDescription = {} # No need for a queue, keeping only the latest is sufficient, since it doens't convey history but the current status.
        self.serviceDescriptions = {}

        # State variables.
        self.alive = True
        self.die   = False
        
        # Other things.
        self.lock = threading.Condition()


    def _serviceRegisteredCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        print "SERVICE REGISTERED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, name=%s, regtype=%s, domain=%s" % (sdRef.fileno(), flags, errorCode, name, regtype, domain)


    def _serviceRegistrationFailedCallback(self, sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        print "SERVICE REGISTRATION FAILED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, errorMessage=%s, name=%s, regtype=%s, domain=%s" % (sdRef, flags, errorCode, errorMessage, name, regtype, domain)


    def _serviceUnregisteredCallback(self, serviceName, serviceType, port):
        print "SERVICE UNREGISTERED CALLBACK FIRED, params: serviceName=%s, serviceType=%s, port=%d" % (serviceName, serviceType, port)


    def _peerServiceDiscoveryCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE DISCOVERY CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)


    def _peerServiceRemovalCallback(self, serviceName, interfaceIndex):
        print "SERVICE REMOVAL CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d" % (serviceName, interfaceIndex)


    def _peerServiceUpdateCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE UPDATE CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)


    def _peerServiceDescriptionUpdatedCallback(self, serviceName, interfaceIndex, txtRecords, updated, deleted):
        print "SERVICE DESCRIPTION UPDATED CALLBACK FIRED", serviceName, interfaceIndex, txtRecords
        print "\tupdated:"
        for key in updated:
            print "\t\t", key, txtRecords[key]
        print "\tdeleted:"
        for key in deleted:
            print "\t\t", key


    def sendMessage(self, destinationUUID, message):
        """Enqueue a message to be sent."""
        with self.lock:
            packet = {}
            packet[destinationUUID] = message
            self.outbox.put(packet)


    def setServiceDescription(self, description):
        """Set the (zeroconf) service description."""
        with self.zeroconf.lock:
            self.zeroconf.outbox.put(description)


    def sendServiceMessage(self, message):
        """Enqueue a service message to be sent."""
        self.sendMessage(self.SERVICE_TO_SERVICE, message)


    def run(self):
        raise NotImplemented


    def kill(self):
        # Let the thread know it should commit suicide.
        with self.lock:
            self.die = True

 
    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Kill multicast and zeroconf.
        self.multicast.kill()
        self.zeroconf.kill()

        # Stop us from running any further.
        self.alive = False




class OneToManyService(Service):
    """One service for many possible destinations per host."""

    def __init__(self, serviceName, serviceType, port, protocolVersion=1):
        super(OneToManyService, self).__init__(serviceName, serviceType, port, protocolVersion)

        # There are multiple destinations per service, so allow for one inbox
        # per destination.
        self.inbox = {}
        # Some messages may not belong to one of the destinations per host,
        # but are meant for host-to-host (service-to-service) communication,
        # hence we also provide a 'global' address: SERVICE_TO_SERVICE.
        self.registerDestination(self.SERVICE_TO_SERVICE)


    def registerDestination(self, destinationUUID):
        with self.lock:
            self.inbox[destinationUUID] = Queue.Queue()


    def removeDestination(self, destinationUUID):
        with self.lock:
            if self.inbox.has_key(destinationUUID):
                del self.inbox[destinationUUID]


    def _multicastRouteIncomingMessages(self):
        """Route incoming multicast messages to the correct destination."""
        with self.lock:
            with self.multicast.lock:
                while self.multicast.inbox.qsize() > 0:
                    packet = self.multicast.inbox.get()
                    # print 'received packet', packet
                    for destinationUUID in packet.keys():
                        if self.inbox.has_key(destinationUUID):
                            # Copy the message from the packet to the
                            # inbox with the correct destination.
                            message = packet[destinationUUID]
                            self.inbox[destinationUUID].put(message)


    def _multicastSendMessages(self):
        """Send outgoing messages."""
        with self.lock:
            with self.multicast.lock:
                while self.outbox.qsize() > 0:
                    # Move the message from the Service outbox to the
                    # multicast messaging outbox, so that it will be sent.
                    message = self.outbox.get()
                    self.multicast.outbox.put(message)


    def _multicastProcessServiceToServiceMessages(self):
        """Process service-to-service messages."""
        with self.lock:
            if self.inbox[self.SERVICE_TO_SERVICE].qsize() > 0:
                message = self.inbox[self.SERVICE_TO_SERVICE].get()
                self._processServiceMessage(message)


    def run(self):
        while self.alive:
            # Multicast messages.
            self._multicastRouteIncomingMessages()
            self._multicastSendMessages()
            self._multicastProcessServiceToServiceMessages()

            # Service descriptions.
            # - updates of our own service description are sent automatically
            #   by buildServiceDescription()
            # - updates of others' service descriptions are processed
            #   automatically through _peerServiceDescriptionUpdatedCallback

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)




class OneToOneService(Service):
    """One service for a single possible destination per host."""

    def __init__(self, serviceName, serviceType, port, protocolVersion=1):
        super(OneToOne, self).__init__(serviceName, serviceType, port, protocolVersion)

        