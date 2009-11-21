import Queue
import threading
from MulticastMessaging import MulticastMessaging


class Service(threading.Thread):


    SERVICE_TO_SERVICE = 'service-to-service'


    def __init__(self, multicastMessagingClass, serviceName, serviceType, protocolVersion=1, port=None):
        # MulticastMessaging subclass.
        if not issubclass(multicastMessagingClass, MulticastMessaging):
            raise MulticastMessagingClassError
        self.multicast = multicastMessagingClass(serviceName, serviceType, protocolVersion, port,
                                                 serviceRegisteredCallback=self._serviceRegisteredCallback,
                                                 serviceRegistrationFailedCallback=self._serviceRegistrationFailedCallback,
                                                 serviceUnregisteredCallback=self._serviceUnregisteredCallback,
                                                 peerServiceDiscoveryCallback=self._peerServiceDiscoveryCallback,
                                                 peerServiceRemovalCallback=self._peerServiceRemovalCallback,
                                                 peerServiceUpdateCallback=self._peerServiceUpdateCallback)
        self.multicast.start()

        # Message storage.
        self.inbox  = Queue.Queue()
        self.outbox = Queue.Queue()
        
        # State variables.
        self.alive = True
        self.die   = False
        
        # Other things.
        self.lock = threading.Condition()

        super(Service, self).__init__()


    def __del__(self):
        self.multicast.kill()


    def _serviceRegisteredCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        print "SERVICE REGISTERED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, name=%s, regtype=%s, domain=%s" % (sdRef.fileno(), flags, errorCode, name, regtype, domain)
        raise NotImplemented


    def _serviceRegistrationFailedCallback(self, sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        print "SERVICE REGISTRATION FAILED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, errorMessage=%s, name=%s, regtype=%s, domain=%s" % (sdRef, flags, errorCode, errorMessage, name, regtype, domain)
        raise NotImplemented


    def _serviceUnregisteredCallback(self, serviceName, serviceType, port):
        print "SERVICE UNREGISTERED CALLBACK FIRED, params: serviceName=%s, serviceType=%s, port=%d" % (serviceName, serviceType, port)
        raise NotImplemented


    def _peerServiceDiscoveryCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE DISCOVERY CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)
        raise NotImplemented


    def _peerServiceRemovalCallback(self, serviceName, interfaceIndex):
        print "SERVICE REMOVAL CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d" % (serviceName, interfaceIndex)
        raise NotImplemented


    def _peerServiceUpdateCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE UPDATE CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)
        raise NotImplemented


    def sendMessage(self, destinationUUID, message):
        """Enqueue a message to be sent."""
        with self.lock:
            packet = {}
            packet[destinationUUID] = message
            self.outbox.put(packet)


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

        # Stop us from running any further.
        self.alive = False




class OneToManyService(Service):
    """One service for many possible destinations per host."""

    def __init__(self, multicastMessagingClass, serviceName, serviceType, protocolVersion=1, port=None):
        super(OneToManyService, self).__init__(multicastMessagingClass, serviceName, serviceType, protocolVersion, port)

        # There are multiple destinations per service, so allow for one inbox
        # per destination.
        self.inbox = {}
        # Some messages may not belong to one of the destinations per host,
        # but are meant for host-to-host (service-to-service) communication,
        # hence we also provide a 'global' address: SERVICE_TO_SERVICE.
        self.inbox[self.SERVICE_TO_SERVICE] = Queue.Queue()


    def registerDestination(self, destinationUUID):
        with self.lock:
            self.inbox[destinationUUID] = Queue.Queue()


    def removeDestination(self, destinationUUID):
        with self.lock:
            if self.inbox.has_key(self.inbox[destinationUUID]):
                del self.inbox[destinationUUID]


    def run(self):
        while self.alive:
            # Route incoming messages to the correct destination.
            with self.lock:
                with self.multicast.lock:
                    while self.multicast.inbox.qsize() > 0:
                        packet = self.multicast.inbox.get()
                        for destinationUUID in packet.keys():
                            if inbox.has_key(destinationUUID):
                                # Copy the message from the packet to the
                                # inbox with the correct destination.
                                message = packet[destinationUUID]
                                inbox[destinationUUID] = message

            # Send outgoing messages.
            with self.lock:
                with self.multicast.lock:
                    while self.outbox.qsize() > 0:
                        # Copy the packet from the Service outbox to the
                        # multicast messaging outbox, so that it will be sent.
                        packet = self.outbox.get()
                        self.multicast.outbox.put(packet)

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)



class OneToOneService(Service):
    """One service for a single possible destination per host."""

    def __init__(self, multicastMessagingClass, serviceName, serviceType, protocolVersion=1, port=None):
        super(OneToOne, self).__init__(multicastMessagingClass, serviceName, serviceType, protocolVersion, port)

        