"""IPMulticastMessaging is a module to make local multicasted, multithreaded,
queued, unordered, unreliable messaging simpler than you can imagine.
Loopback is enabled.
(Fragmentation and reassembly happen automatically. Unreliable because no
recovery/resending happens for lost packets.)
Uses IP multicast networking."""


import select
import cPickle
import math
import Queue
import socket
import threading
import time
import uuid

import netstring


# TODO: investigate if netstrings are still necessary, I'm pretty sure they aren't.

# Define exceptions.
class IPMulticastMessagingError(Exception): pass
class MessageTooLargeError(IPMulticastMessagingError): pass
class SentIncompleteMessageError(IPMulticastMessagingError): pass


class IPMulticastMessaging(threading.Thread):

    ANY = "0.0.0.0" # Corresponds to INADDR_ANY.
    MCAST_GRP = '225.0.13.37'
    MCAST_TTL = 1 # 1 for same subnet, 32 for same organization (see http://www.tldp.org/HOWTO/Multicast-HOWTO-2.html)
    PACKET_SIZE = 150
    MAX_NUM_FRAGMENTS = 10000

    FRAGMENT_ID_SIZE   = 36 + 5 + 5 # UUID (32 characters) + number (5 digits) + total number (5 digits)
    FRAGMENT_DATA_SIZE = PACKET_SIZE - FRAGMENT_ID_SIZE

    def __init__(self, port):
        super(IPMulticastMessaging, self).__init__(name="IPMulticastMessaging-Thread")

        # Message relaying.
        self.inbox  = Queue.Queue()
        self.outbox = Queue.Queue()

        # Metadata.
        self.fragmentsBuffer = {}
        self.memberships     = []

        # Mutual exclusion.
        self.lock = threading.Condition()

        # General state variables.
        self.alive = True
        self.die   = False

        # Bind to socket for receiving IP multicast packets.
        self.recvSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.recvSocket.setblocking(0)
        self.recvSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'SO_REUSEPORT'):
            self.recvSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) # Allow multiple processes on the same computer to join the multicast group.
        self.recvSocket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.MCAST_TTL) 
        self.recvSocket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1) # Enable loopback.
        self.recvSocket.bind((self.ANY, port))
        # SAMPLE: If we'd like to use a specific network InterFace (IF).
        # host = socket.gethostbyname(socket.gethostname())
        # self.recvSocket.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
        # SAMPLE: If we'd like to subscribe to multicast packets for the given
        # multicast group on *all* network intefaces.
        # self.recvSocket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(self.ANY))
        # Find out which random port was picked.
        if port == 0:
            (ip, port) = self.recvSocket.getsockname()
            self.recvPort = int(port)
        else:
            self.recvPort = int(port)
        # Subscribe to all of our own IPs so that our own messages will be
        # accepted as any other.
        (hostname, aliaslist, ipaddrlist) = socket.gethostbyname_ex(socket.gethostname())
        for ip in ipaddrlist:
            self.subscribe(ip)

        # Prepare socket for sending IP multicast packets. Always picks a
        # random port. Also necessary for zeroconf: if you pass it the same
        # address/port combination twice, it will think that you're registering
        # the same service twice and not resolve name conflicts automatically
        # (which can happen if you're running multiple instances on the same
        # host).
        self.sendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sendSocket.setblocking(0)
        self.sendSocket.bind((self.ANY, 0))
        (ip, port) = self.sendSocket.getsockname()
        self.sendPort = port


    def getSendPort(self):
        return self.sendPort


    def run(self):
        while self.alive:
            # Send and receive IP multicast messages.
            self._send()
            self._receive()

            # Commit suicide when asked to.
            with self.lock:
                if self.die and self.outbox.qsize() == 0:
                    self._commitSuicide()

            # Processing the queues 50 times per second is sufficient.
            time.sleep(0.02)

    def subscribe(self, host):
        if host not in self.memberships:
            self.memberships.append(host)
            self.recvSocket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(host))
            # print "subscribed to %s" % host
            return True
        else:
            # Already subscribed.
            return False


    def unsubscribe(self, host):
        self.memberships.remove(host)
        self.recvSocket.setsockopt(socket.SOL_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(host))


    def kill(self):
        # Let the thread know it should commit suicide.
        with self.lock:
            self.die = True


    def _send(self):
        """Send all messages waiting to be sent in the outbox."""

        with self.lock:
            while self.outbox.qsize() > 0:
                self._sendMessage(self.outbox.get())


    def _sendMessage(self, message):
        """Helper method for _send()."""

        # First pickle the value so we get a string (the message may contain
        # *any* possible Python value). Then encode it as a netstring so we
        # can reassemble the data after it's been fragmented to fit in the
        # configured packet size.
        # (UDP doesn't do fragmentation and requires a fixed packet size and
        # thus we must handle fragmentation ourselves.)
        data = netstring.encode(cPickle.dumps(message))

        # Fragment the data into multiple packets when there's too much data
        # to fit in a single packet.
        bytesData       = len(data)
        bytesFragmented = 0 # At the end, this must match the bytesData.
        packetID        = str(uuid.uuid1()) # Generate a UUID for the packet.
        numFragments    = int(math.ceil(1.0 * bytesData / self.FRAGMENT_DATA_SIZE))
        fragments       = []
        # Ensure that the number of fragments does not exceed 10,000.
        if numFragments > self.MAX_NUM_FRAGMENTS:
            raise MessageTooLargeError, "Too many fragments were necessary to send the data: %d, while 10,000 is the limit." % (len(numFragments))
        for f in xrange(numFragments):
            # Create the fragment ID.
            fragmentID = self._createFragmentID(packetID, f, numFragments)
            # Create the fragment data.
            fragmentData = data[:self.FRAGMENT_DATA_SIZE]
            bytesFragmented += len(fragmentData)
            # Combine the ID and the data into the actual fragment.
            fragment = fragmentID + fragmentData
            fragments.append(fragment)
            # print 'FRAGMENT', fragmentID, ', fragment size:', len(fragment), ', bytes Fragmented:', bytesFragmented, ', more:', bytesFragmented < bytesData
            # Update the remaining data that should be sent.
            data = data[self.FRAGMENT_DATA_SIZE:]
        # Ensure that all data is sent.
        if bytesFragmented != bytesData:
            raise SentIncompleteMessageError, "Not everything is sent, only %d bytes out of %d!" % (bytesFragmented, bytesData)

        # Actually send all created fragments.
        for fragment in fragments:
            self.sendSocket.sendto(fragment, (self.MCAST_GRP, self.recvPort))


    def _createFragmentID(self, packetID, fragmentSeqNum, numFragments):
        return "%s%05d%05d" % (packetID, fragmentSeqNum, numFragments)


    def _parseFragmentID(self, fragmentID):
        """Parse a fragment ID. The first 32 characters are a UUID, the next 5
        characters form an integer with leading zeros and indicate the
        sequence number of the fragment and the final 5 characters also form
        an integer with leading zeros but indciates the total number of
        fragments for the packet."""
        # print "\tparsed FRAGMENT ID", fragmentID, (fragmentID[0:36], int(fragmentID[36:41]), int(fragmentID[41:46]))
        return (fragmentID[0:36], int(fragmentID[36:41]), int(fragmentID[41:46]))


    def _receive(self):
        """Send all messages waiting to be sent in the outbox."""

        # Check if there's input on the socket that we've bound for multicast
        # traffic.
        inputReady, outputReady, exceptReady = select.select([self.recvSocket], [], [], 0)
        if self.recvSocket in inputReady:
            for message in self._receiveMessage():
                self.inbox.put(message)


    def _receiveMessage(self):
        try:
            data, addr = self.recvSocket.recvfrom(self.PACKET_SIZE)
            # print 'RECEIVED MESSAGE FROM:', addr, addr[0] in self.memberships
        except socket.error, e:
            print 'Expection'

        # Discard messages from hosts we're not interested in.
        # NOTE: this requires discovery of other hosts through another means
        # than IP multicast itself, e.g. zeroconf.
        if addr[0] not in self.memberships:
            return
        # print 'RECEIVED MESSAGE FROM:', addr, addr[0] in self.memberships

        # Extract the fragment ID from the data.
        fragmentID = data[:self.FRAGMENT_ID_SIZE]
        data = data[self.FRAGMENT_ID_SIZE:]

        # Parse the fragment ID.
        packetID, sequenceNumber, totalNumber = self._parseFragmentID(fragmentID)

        # Reassemble the packet.
        packet = ""
        if totalNumber > 1:
            # Handle fragmentation.
            if not self.fragmentsBuffer.has_key(packetID):
                self.fragmentsBuffer[packetID] = {}
            self.fragmentsBuffer[packetID][sequenceNumber] = data
            # When we have all fragments of a packet, reassemble the packet.
            if len(self.fragmentsBuffer[packetID]) == totalNumber:
                for key in xrange(totalNumber):
                    packet += self.fragmentsBuffer[packetID][key]
                del self.fragmentsBuffer[packetID]
        else:
            # This packet consists of a single frame: no need to reassemble!
            packet = data

        # Decode the message in the packet.
        if packet != "":
            # Attempt to decode netstrings from the buffer.
            try:
                netstrings, remaining = netstring.decode(packet)
                if len(remaining) > 0:
                    raise Exception, "No data should be remaining."
                for string in netstrings:
                    with self.lock:
                        # WARNING: insecure! Global variables might be
                        # unpickled!
                        message = cPickle.loads(string)
                        yield message
            except netstring.DecoderError:
                pass


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """
        # Drop memberships.
        while len(self.memberships): # Tricky: we cannot simply iterate over the list because we're changing it!
            host = self.memberships[0]
            self.unsubscribe(host)

        # Close sockets.
        self.sendSocket.close()
        self.recvSocket.close()

        # Stop us from running any further.
        self.alive = False




if __name__ == "__main__":
    import time
    import platform
    import copy
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-l", "--listenOnly", action="store_true", dest="listenOnly",
                      help="listen only (don't broadcast)")

    (options, args) = parser.parse_args()

    # Initialize IPMulticastMessaging.
    mc = IPMulticastMessaging(port = 1600)

    # Prepare two messages to be broadcast.
    message = {
        'status'           : 'playing',
        'playerName'       : 'Wim',
        'hostedGame'       : "Wim's game",
        'participatedGame' : "Wim's game",
        'players'          : [3],
        'timePlaying'      : 123,
        'newMoves'         : [(3245, 'Brecht', 2), (3246, 'Kristof', 3)],
    }
    messageTwo = copy.deepcopy(message)
    messageTwo['players'] = 2
    del messageTwo['newMoves']

    # Sample usage.
    mc.start()
    if not options.listenOnly:
        # Put messages in the outbox.
        time.sleep(2)
        with mc.lock:
            mc.outbox.put(message)
        time.sleep(2)
        with mc.lock:
            mc.outbox.put(messageTwo)
        endTime = time.time() + 4
    else:
        endTime = time.time() + 10
    # Get messages from the inbox.
    with mc.lock:
        # Keep fetching messages until the end time has been reached.
        while time.time() < endTime:
            # Wait for a next message.
            while mc.inbox.qsize() == 0 and time.time() < endTime:
                mc.lock.wait(1) # Timeout after 1 second of waiting.
            if mc.inbox.qsize() > 0:
                message = mc.inbox.get()
                print "MESSAGE IN INBOX", message
    mc.kill()
