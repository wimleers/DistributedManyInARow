import Queue
import threading


class MulticastMessaging(threading.Thread):
    """Base class for multicast messaging. Can be used in unit tests to
    manually fill the inbox and outbox queues, so you don't have to rely on
    actual network traffic.
    """

    def __init__(self, serviceName, serviceType, protocolVersion=1, port=None,
                 serviceRegisteredCallback=None,
                 serviceRegistrationFailedCallback=None,
                 peerServiceDiscoveryCallback=None,
                 peerServiceRemovalCallback=None,
                 peerServiceUpdateCallback=None,
                 peerMessageCallback=None):
        super(MulticastMessaging, self).__init__()

        # Metadata.
        self.serviceName     = serviceName
        self.serviceType     = serviceType
        self.protocolVersion = protocolVersion
        self.port            = port
        # Message relaying.
        self.inbox  = Queue.Queue()
        self.outbox = Queue.Queue()
        # Mutual exclusion.
        self.lock = threading.Condition()

    def run(self):
        raise NotImplemented


    def kill(self):
        raise NotImplemented
    