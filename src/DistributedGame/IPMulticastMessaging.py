"""IPMulticastMessaging is a module to make local multicasted, multithreaded,
queued unordered, reliable messaging simpler than you can imagine. Peer
discovery happens automatically. Naming conflicts are solved automatically.
Forget IGMP and special hardware requirements.
Uses zeroconf networking."""


import select
import cPickle
import math
import socket
import time
import uuid

import netstring
import pybonjour

from MulticastMessaging import MulticastMessaging


# The protocol version is stored automatically in the primary TXT record and
# associated with a "textvers" key, as is the convention in Bonjour/zeroconf.


# Define exceptions.
class IPMulticastMessagingError(Exception): pass
class InvalidCallbackError(IPMulticastMessagingError): pass
class MessageTooLargeError(IPMulticastMessagingError): pass
class ProtocolVersionMismatch(IPMulticastMessagingError): pass


# Copied from django.utils.functional
def curry(_curried_func, *args, **kwargs):
    def _curried(*moreargs, **morekwargs):
        return _curried_func(*(args+moreargs), **dict(kwargs, **morekwargs))
    return _curried


class IPMulticastMessaging(MulticastMessaging):

    ANY = "0.0.0.0" # Corresponds to INADDR_ANY.
    MCAST_GRP = '225.0.13.37'
    MCAST_TTL = 1 # 1 for same subnet, 32 for same organization (see http://www.tldp.org/HOWTO/Multicast-HOWTO-2.html)
    PACKET_SIZE = 150

    FRAGMENT_ID_SIZE   = 36 + 5 + 5 # UUID (32 characters) + number (5 digits) + total number (5 digits)
    FRAGMENT_DATA_SIZE = PACKET_SIZE - FRAGMENT_ID_SIZE

    def __init__(self, serviceName, serviceType, protocolVersion=1, port=None,
                 serviceRegisteredCallback=None,
                 serviceRegistrationFailedCallback=None,
                 serviceUnregisteredCallback=None,
                 peerServiceDiscoveryCallback=None,
                 peerServiceRemovalCallback=None,
                 peerServiceUpdateCallback=None,
                 peerServiceDescriptionUpdatedCallback=None,
                 peerMessageCallback=None):
        super(IPMulticastMessaging, self).__init__(serviceName, serviceType)

        # Ensure the callbacks are valid.
        if not callable(serviceRegisteredCallback):
            raise InvalidCallbackError, "service registered callback"
        if not callable(serviceRegistrationFailedCallback):
            raise InvalidCallbackError, "service registration failed callback"
        if not callable(serviceUnregisteredCallback):
            raise InvalidCallbackError, "service unregistered callback"
        if not callable(peerServiceDiscoveryCallback):
            raise InvalidCallbackError, "peer service discovery callback"
        if not callable(peerServiceRemovalCallback):
            raise InvalidCallbackError, "peer service removal callback"
        if not callable(peerServiceUpdateCallback):
            raise InvalidCallbackError, "peer service update callback"
        if not callable(peerServiceDescriptionUpdatedCallback):
            raise InvalidCallbackError, "peer service description updated callback"
        if not callable(peerMessageCallback):
            raise InvalidCallbackError, "peer message callback"

        # Callbacks.
        self.serviceRegisteredCallback             = serviceRegisteredCallback
        self.serviceRegistrationFailedCallback     = serviceRegistrationFailedCallback
        self.serviceUnregisteredCallback           = serviceUnregisteredCallback
        self.peerServiceDiscoveryCallback          = peerServiceDiscoveryCallback
        self.peerServiceRemovalCallback            = peerServiceRemovalCallback
        self.peerServiceUpdateCallback             = peerServiceUpdateCallback
        self.peerServiceDescriptionUpdatedCallback = peerServiceDescriptionUpdatedCallback
        self.peerMessageCallback                   = peerMessageCallback

        # Zeroconf metadata for tracking changes in our own service description.
        self.txtRecords = {}
        # Zeroconf metadata for tracking changes in peers' service descriptions.
        self.peers                                   = {}
        self.peersTxtRecords                         = {}
        self.peersTxtRecordsUpdatedSinceLastCallback = {}
        self.peersTxtRecordsDeletedSinceLastCallback = {}
        # Zeroconf state variables.
        self.serverReady = False
        self.clientReady = False
        # Zeroconf service descriptor references.
        self.sdRefServer           = None # A single sdRef to send messages.
        self.sdRefBrowse           = None # A single sdRef to discover peers.
        self.sdRefSingleShots      = []   # A list of sdRefs that need to return something just once.
        self.sdRefTXTRecordQueries = []   # A list of sdRefs that are "long-lived", always awaiting new/updated TXT records.

        # Multicast metadata.
        self.stringAssembler = netstring.Decoder()
        self.fragmentsBuffer = {}
        self.buffer = ""
        # Multicast memberships.
        self.memberships = []

        # General state variables.
        self.alive       = True
        self.die         = False

        # If port is set to None, then pick a random free port automatically.
        if port is None:
            port = 0
        else:
            port = port
        # Bind to socket for receiving IP multicast packets.
        self.recvSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.recvSocket.setblocking(0)
        self.recvSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
        # Subscribe to ourself: apparently, enabling IP_MULTICAST_LOOP is not
        # sufficient.
        host = socket.gethostbyname(socket.gethostname())
        self.subscribe(host)

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


    def run(self):
        # Register zeroconf service.
        self._registerZeroconfService()

        # Browse peers' zeroconf services.
        self._browseZeroconfServices()

        while self.alive:
            # Process responses of the zeroconf server (register, browse,
            # resolve, query callbacks).
            self._processResponses()

            # When zeroconf service registration has been completed, send
            # updates in our own service description and track updates of
            # peers' service descriptions:
            if self.serverReady:
                pass
                # 1) send multicast messages waiting in the outbox.

                # 2) receive multicast messages.
                # Messages are received through _queryTXTRecordCallback() and
                # are put in the inbox directly from there.

            # Send and receive IP multicast messages.
            self._send()
            self._receive()

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # Processing the queues 50 times per second is sufficient.
            time.sleep(0.02)


    def subscribe(self, host):
        if host not in self.memberships:
            self.memberships.append(host)
            self.recvSocket.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.MCAST_GRP) + socket.inet_aton(host))
            print "subscribed to %s" % host
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


    def _registerZeroconfService(self):
        """Register the DNS service, along with a primary TXT record, which
        will contain the protocol version.
        Must only be called once.
        """
        primaryTxtRecord = pybonjour.TXTRecord()
        primaryTxtRecord['textvers'] = self.protocolVersion
        self.sdRefServer = pybonjour.DNSServiceRegister(name = self.serviceName,
                                                        regtype = self.serviceType,
                                                        port = self.sendPort,
                                                        txtRecord = primaryTxtRecord,
                                                        callBack = self._serviceRegisteredCallback)


    def _browseZeroconfServices(self):
        """Browse to find hosts that offer the same service.
        Must only be called once, because it will continue indefinitely.
        """
        self.sdRefBrowse = pybonjour.DNSServiceBrowse(regtype = self.serviceType,
                                                      callBack = self._browseCallback)
        self.clientReady = True


    def _browseCallback(self, sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return
        else:
            # TODO: add optional error callback?
            pass

        # Discovering our own service doesn't count.
        if serviceName == self.serviceName:
            return

        # Rediscovering an already discovered service (e.g. due to a new or
        # updated TXT record) on the same interface also doesn't count.
        if serviceName in self.peers.keys() and interfaceIndex in self.peers[serviceName].keys():
            return

        # If no service is being added, then one is being removed.
        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            self.peerServiceRemovalCallback(serviceName, interfaceIndex)
            del self.peers[serviceName][interfaceIndex]
            if len(self.peers[serviceName]) == 0:
                del self.peers[serviceName]
            return

        # Create curried callbacks so we can pass additional data to the
        # resolve callback.
        curriedCallback = curry(self._resolveCallback,
                                serviceName = serviceName)
    
        # We've found a peer with the same service, but now we still have to
        # determine the details: full name, host target, port, primary
        # TXT record and IP address.
        sdRef = pybonjour.DNSServiceResolve(0,
                                            interfaceIndex,
                                            serviceName,
                                            regtype,
                                            replyDomain,
                                            curriedCallback)
        self.sdRefSingleShots.append(sdRef)


    def _resolveCallback(self, sdRef, flags, interfaceIndex, errorCode, fullname, hosttarget, port, txtRecord, serviceName):
        """Callback for DNSServiceResolve(). serviceName should be curried."""

        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return
        else:
            # TODO: add optional error callback?
            pass

        # Only changes in either of these will result in updated service
        # metadata, and the associated peerServiceUpdateCallback callback.
        updatedServiceKeys = ['fullname', 'hosttarget', 'port']

        metadata = {
            'serviceName' : serviceName,
            'fullname' : fullname,
            'hosttarget' : hosttarget,
            'port' : port,
        }

        # Store metadata.
        if not serviceName in self.peers.keys():
            self.peers[serviceName] = {}
        # Initial resolve: new service: store metadata and look up the IP
        # address.
        if interfaceIndex not in self.peers[serviceName].keys():
            self.peers[serviceName][interfaceIndex] = metadata

            # Create a curried callback so we can pass additional data to the
            # (single-shot) A query record callback.
            curriedCallback = curry(self._queryARecordCallback,
                                    serviceName = serviceName,
                                    hosttarget = hosttarget,
                                    port = port)

            # Retrieve the IP address by querying the peer's A record.
            sdRef = pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
                                                    fullname = hosttarget,
                                                    rrtype = pybonjour.kDNSServiceType_A,
                                                    callBack = curriedCallback)
            self.sdRefSingleShots.append(sdRef)

            # Create a curried callback so we can pass additional data to the
            # (long-lived) TXT query record callback.
            curriedCallback = curry(self._queryTXTRecordCallback,
                                    serviceName = serviceName,
                                    hosttarget = hosttarget, # TRICKY: A record has name like "_http._tcp.local", hence use hosttarget.
                                    port = port)

            # Monitor this service's TXT records.
            sdRef = pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
                                                    flags = pybonjour.kDNSServiceFlagsLongLivedQuery,
                                                    fullname = fullname, # TRICKY: TXT record has name like "My Web Server._http._tcp.local", hence use fullname.
                                                    rrtype = pybonjour.kDNSServiceType_TXT,
                                                    callBack = curriedCallback)
            self.sdRefTXTRecordQueries.append(sdRef)


        # Secondary resolves: updated service or simply different txtRecords.
        # Ignore multiple resolves for the same service (this happens when
        # a service has multiple TXT records, see
        # http://code.google.com/p/pybonjour/issues/detail?id=2).
        else:
            # Only certain changes in metadata will result in an update. Build
            # dictionaries containing just these values.
            curMetadata = {}
            newMetadata = {}
            for key in updatedServiceKeys:
                curMetadata[key] = metadata[key]
                newMetadata[key] = self.peers[serviceName][interfaceIndex][key]
            # If the metadata differs: updated service.
            if curMetadata != newMetadata:
                for key in updatedServiceKeys:
                    self.peers[serviceName][interfaceIndex][key] = metadata[key]
                self.peerServiceUpdateCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port, txtRecord)


    def _queryARecordCallback(self, sdRef, flags, interfaceIndex, errorCode, fullname, rrtype, rrclass, rdata, ttl, serviceName, hosttarget, port):
        """Callback for DNSServiceQueryRecord(). serviceName, hosttarget and 
        port should be curried.
        """

        if errorCode == pybonjour.kDNSServiceErr_NoError:
            # We've now got *all* information about the peer with the same
            # service. Time to call the callback.
            ip = socket.inet_ntoa(rdata)
            if not serviceName in self.peers.keys():
                self.peers[serviceName] = {}
            self.peers[serviceName][interfaceIndex] = {
                'serviceName' : serviceName,
                'fullname' : fullname,
                'hosttarget' : hosttarget,
                'ip' : ip,
                'port' : port,
            }
            self.peerServiceDiscoveryCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port)
        else:
            # TODO: add optional error callback?
            pass


    def _queryTXTRecordCallback(self, sdRef, flags, interfaceIndex, errorCode, fullname, rrtype, rrclass, rdata, ttl, serviceName, hosttarget, port):
        # Parse the data directly, without using pybonjour.TXTRecord. The code
        # would be uglier and less efficient, because we always store a single
        # key-value pair, whereas the specification allows for multiple pairs.
        length = ord(rdata[0])
        key, value = rdata[1:length+1].split('=', 1)

        # When the TTL is zero, a record has been "removed". In reality, this
        # is only broadcast when a record has been *updated*, not removed
        # (when a record is removed, nothing is broadcast). The new value is
        # included in the same broadcast and therefor this callback function
        # will be called again for this TXT record, but then containing the
        # updated value. Hence we can ignore this callback.
        if ttl == 0:
            return

        # When the key is "textvers", verify the protocol version.
        if key == 'textvers':
            if str(value) != str(self.protocolVersion):
                # Remove this peer since it doesn't have a matching protocol
                # version anyway.
                self.sdRefTXTRecordQueries.remove(sdRef)
                del self.peers[serviceName]
                raise ProtocolVersionMismatch, "Removed peer '%s' due to protol version mismatch. Own protocol version: %s, other protocol version: %s." % (serviceName, self.protocolVersion, value)
            return

        # Keep track of all TXT records.
        if serviceName not in self.peersTxtRecords.keys():
            self.peersTxtRecords[serviceName] = {}
            self.peersTxtRecordsUpdatedSinceLastCallback[serviceName] = {}
            self.peersTxtRecordsDeletedSinceLastCallback[serviceName] = {}
        if interfaceIndex not in self.peersTxtRecords[serviceName].keys():
            self.peersTxtRecords[serviceName][interfaceIndex] = {}
            self.peersTxtRecordsUpdatedSinceLastCallback[serviceName][interfaceIndex] = []
            self.peersTxtRecordsDeletedSinceLastCallback[serviceName][interfaceIndex] = []
        # When the value is 'DELETE', delete the corresponding key from the
        # TXT records. Else, unpickle the value and update our local mirror
        # of the peer's TXT records (and remember which records have been
        # updated, so we can send a single callback for multiple changes).
        if value == 'DELETE':
            if serviceName in self.peersTxtRecords.keys():
                if interfaceIndex in self.peersTxtRecords[serviceName].keys():
                    if key in self.peersTxtRecords[serviceName][interfaceIndex].keys():
                        del self.peersTxtRecords[serviceName][interfaceIndex][key]
            self.peersTxtRecordsDeletedSinceLastCallback[serviceName][interfaceIndex].append(key)
        # Else, this is either a new or updated key-value pair. Mark the key
        # as having an update and store the pickled value.
        else:
            self.peersTxtRecordsUpdatedSinceLastCallback[serviceName][interfaceIndex].append(key)
            self.peersTxtRecords[serviceName][interfaceIndex][key] = cPickle.loads(value)

        # Only put messages in the inbox when no more TXT record changes are
        # coming from this service/interface combo.
        if not (flags & pybonjour.kDNSServiceFlagsMoreComing):
            # Get the TXT records and the keys of the updated and deleted TXT
            # records.
            txtRecords = self.peersTxtRecords[serviceName][interfaceIndex]
            updated    = self.peersTxtRecordsUpdatedSinceLastCallback[serviceName][interfaceIndex]
            deleted    = self.peersTxtRecordsDeletedSinceLastCallback[serviceName][interfaceIndex]
            # Erase the lists of keys of updated and deleted TXT records for
            # the next time.
            self.peersTxtRecordsUpdatedSinceLastCallback[serviceName][interfaceIndex] = []
            self.peersTxtRecordsDeletedSinceLastCallback[serviceName][interfaceIndex] = []
            # Send the callback, if it is callable.
            if callable(self.peerMessageCallback):
                self.peerMessageCallback(serviceName, interfaceIndex, txtRecords, updated, deleted)
            # # Update the inbox. Only send the message itself, not the details.
            # with self.lock:
            #     message = [{header : txtRecords[header]} for header in updated]
            #     if len(message):
            #         self.inbox.put(message)
            #         self.lock.notifyAll()


    def _processResponses(self):
        # Process responses for server (i.e. registration callback, TXT record
        # updates).
        if self.sdRefServer is not None:
            self._processResponsesForService(self.sdRefServer)

        # Process responses for client (i.e. detecting peers with a matching
        # service type and peers' updated TXT records).
        if self.serverReady and self.clientReady and self.sdRefBrowse is not None:
            self._processResponsesForService(self.sdRefBrowse)

        # Process responses for one shot service descriptor references (i.e.
        # resolve and A record query callbacks). These service descriptor
        # references must be closed as soon as we get input (hence "one shot").
        for sdRef in self.sdRefSingleShots:
            if self._processResponsesForService(sdRef):
                self.sdRefSingleShots.remove(sdRef)
                sdRef.close()

        # Process responses for "long-lived" service descriptor references
        # (i.e. TXT record query callbacks).
        for sdRef in self.sdRefTXTRecordQueries:
            self._processResponsesForService(sdRef)


    def _processResponsesForService(self, sdRef):
        """Helper function for _procesResponses(). Returns True when input was
        ready, False otherwise."""

        # If there's input waiting to be processed, process it. Only wait
        # for input for 0.05 seconds (avoid blocking).
        inputReady, outputReady, exceptReady = select.select([sdRef], [], [], 0.05)
        if sdRef in inputReady:
            pybonjour.DNSServiceProcessResult(sdRef)
            return True

        return False


    def _serviceRegisteredCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        # Call the appropriate external callback.
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            # Update our own service name.
            self.serviceName = name
            self.serverReady = True
            # Call the service registration callback.
            self.serviceRegisteredCallback(sdRef, flags, errorCode, name, regtype, domain, self.sendPort)
        else:
            # Call the error callback, and pass it the error message.
            errorMessage = pybonjour.BonjourError._errmsg[errorCode]
            self.serviceRegistrationFailedCallback(sdRef, flags, errorCode, errorMessage, name, regtype, domain)


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
        if numFragments > 10000:
            raise Exception, "Too many fragments were necessary to send the data: %d, while 10,000 is the limit." % (len(numFragments))
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
            raise Exception, "Not everything is sent, only %d bytes out of %d!" % (bytesFragmented, bytesData)

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
        except socket.error, e:
            print 'Expection'

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
                        print 'RECEIVED MESSAGE FROM:', addr, addr[0] in self.memberships
                        yield message
                
            except netstring.DecoderError:
                pass
        
        
        # newTxtRecords = {}
        #         for key, value in message.items():
        #             serializedValue = cPickle.dumps(value)
        #             # Validate TXT record size: it should never exceed 65536 bytes.
        #             if len(key) + len('=') + len(serializedValue) > 65536:
        #                 raise MessageTooLargeError, "message size is: %d for key '%s'" % (len(key) + len('=') + len(serializedValue), key)
        #             txt = pybonjour.TXTRecord({key : serializedValue}, False) # Disable strict checking, which would only allow for 255 bytes.
        #             newTxtRecords[key] = {'value' : value, 'txtRecord' : txt}
        # 
        #         # Make sets out of the keys of the TXT records to make it easier to
        #         # determine what should happen.
        #         curKeys = set(self.txtRecords.keys())
        #         newKeys = set(newTxtRecords.keys())
        # 
        #         # Update: intersection of current and new TXT records, plus a value
        #         # comparison to ensure we only update when the value actually changed.
        #         for key in curKeys.intersection(newKeys):
        #             if self.txtRecords[key]['value'] != newTxtRecords[key]['value']:
        #                 print "\tUpdating:", key
        #                 pybonjour.DNSServiceUpdateRecord(sdRef = self.sdRefServer,
        #                                                  RecordRef = self.txtRecords[key]['recordReference'],
        #                                                  rdata = newTxtRecords[key]['txtRecord'])
        #                 # Update the stored TXT record.
        #                 self.txtRecords[key]['txtRecord'] = newTxtRecords[key]['txtRecord']
        #                 self.txtRecords[key]['value']     = newTxtRecords[key]['value']
        # 
        #         # Remove: difference of current with new TXT records.
        #         for key in curKeys.difference(newKeys):
        #             print "\tRemoving: ", key
        #             # A removed record doesn't get broadcast. So first update the
        #             # record's value to the string 'DELETE'. This is our way of
        #             # telling that this TXT record will be deleted.
        #             pybonjour.DNSServiceUpdateRecord(sdRef = self.sdRefServer,
        #                                              RecordRef = self.txtRecords[key]['recordReference'],
        #                                              rdata = pybonjour.TXTRecord({key : 'DELETE'}))
        #             # Now actually remove the record.
        #             # TRICKY: this doesn't have to ever happen. See the above comment.
        #             # pybonjour.DNSServiceRemoveRecord(sdRef = self.sdRefServer,
        #             #                                  RecordRef = self.txtRecords[key]['recordReference'])
        #             # Remove the stored TXT record.
        #             del self.txtRecords[key]
        # 
        #         # Add: difference of new with current TXT records.
        #         for key in newKeys.difference(curKeys):
        #             print "\tAdding:", key
        #             rdlen, rdata = pybonjour._string_to_length_and_void_p(newTxtRecords[key]['txtRecord'])
        #             rRef = pybonjour.DNSServiceAddRecord(sdRef = self.sdRefServer,
        #                                                  rrtype = pybonjour.kDNSServiceType_TXT,
        #                                                  rdata = newTxtRecords[key]['txtRecord'])
        #             # Store the new TXT record.
        #             self.txtRecords[key] = newTxtRecords[key]
        #             # Also store the record reference.
        #             self.txtRecords[key]['recordReference'] = rRef


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Close the service descriptor references.
        if self.sdRefServer is not None:
            self.sdRefServer.close()
            # We've now unregistered our service, thus call the
            # serviceUnregisteredCallback callback.
            self.serviceUnregisteredCallback(self.serviceName, self.serviceType, self.sendPort)
        if self.sdRefBrowse is not None:
            self.sdRefBrowse.close()
        for sdRef in self.sdRefSingleShots:
            sdRef.close()
        for sdRef in self.sdRefTXTRecordQueries:
            sdRef.close()

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

    def serviceRegisteredCallback(sdRef, flags, errorCode, name, regtype, domain, port):
        print "SERVICE REGISTERED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, name=%s, regtype=%s, domain=%s, port=%d" % (sdRef.fileno(), flags, errorCode, name, regtype, domain, port)

    def serviceRegistrationFailedCallback(sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        print "SERVICE REGISTRATION FAILED CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, errorMessage=%s, name=%s, regtype=%s, domain=%s" % (sdRef, flags, errorCode, errorMessage, name, regtype, domain)

    def serviceUnregisteredCallback(serviceName, serviceType, port):
        print "SERVICE UNREGISTERED CALLBACK FIRED, params: serviceName=%s, serviceType=%s, port=%d" % (serviceName, serviceType, port)

    def peerServiceDiscoveryCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE DISCOVERY CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)
        z.subscribe(ip)

    def peerServiceRemovalCallback(serviceName, interfaceIndex):
        print "SERVICE REMOVAL CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d" % (serviceName, interfaceIndex)

    def peerServiceUpdateCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE UPDATE CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

    def peerServiceDescriptionUpdatedCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE DESCRIPTION UPDATED CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

    def peerMessageCallback(serviceName, interfaceIndex, txtRecords, updated, deleted):
        print "PEER MESSAGE CALLBACK FIRED", serviceName, interfaceIndex, txtRecords
        print "\tupdated:"
        for key in updated:
            print "\t\t", key, txtRecords[key]
        print "\tdeleted:"
        for key in deleted:
            print "\t\t", key

    parser = OptionParser()
    parser.add_option("-l", "--listenOnly", action="store_true", dest="listenOnly",
                      help="listen only (don't broadcast)")

    (options, args) = parser.parse_args()

    # Initialize IPMulticastMessaging.
    z = IPMulticastMessaging(serviceName = platform.node(),
                          serviceType = '_manyinarow._tcp',
                          protocolVersion = 1,
                          port = 1600,
                          serviceRegisteredCallback=serviceRegisteredCallback,
                          serviceRegistrationFailedCallback=serviceRegistrationFailedCallback,
                          serviceUnregisteredCallback=serviceUnregisteredCallback,
                          peerServiceDiscoveryCallback=peerServiceDiscoveryCallback,
                          peerServiceRemovalCallback=peerServiceRemovalCallback,
                          peerServiceUpdateCallback=peerServiceUpdateCallback,
                          peerServiceDescriptionUpdatedCallback=peerServiceDescriptionUpdatedCallback,
                          peerMessageCallback=peerMessageCallback)
     
 
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
    z.start()
    if not options.listenOnly:
        # Put messages in the outbox.
        time.sleep(5)
        with z.lock:
            z.outbox.put(message)
        time.sleep(2)
        with z.lock:
            z.outbox.put(messageTwo)
    # Get messages from the inbox.
    with z.lock:
        endTime = time.time() + 10
        # Keep fetching messages until the end time has been reached.
        while time.time() < endTime:
            # Wait for a next message.
            while z.inbox.qsize() == 0 and time.time() < endTime:
                z.lock.wait(1) # Timeout after 1 second of waiting.
            if z.inbox.qsize() > 0:
                message = z.inbox.get()
                print "MESSAGE IN INBOX", message
    z.kill()
