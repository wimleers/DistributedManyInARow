"""Neighborhood is a module to make local multicasted, multithreaded, queued
messaging simpler than you can imagine. Peer discovery happens automatically.
Naming conflicts are solved automatically. Forget IGMP and special hardware
requirements.
Uses zeroconf networking."""


import select
import pybonjour
import threading
import Queue
import cPickle
import socket
import time


# The protocol version is stored automatically in the primary TXT record and
# associated with a "textvers" key, as is the convention in Bonjour/zeroconf.


# TODO: add the ability to act as a relay node, i.e. to pass received
# messages through to nodes on other interfaces.


# Define exceptions.
class NeighborhoodError(Exception): pass
class InvalidCallbackError(NeighborhoodError): pass
class MessageTooLargeError(NeighborhoodError): pass
class ProtocolVersionMismatch(NeighborhoodError): pass


# Copied from django.utils.functional
def curry(_curried_func, *args, **kwargs):
    def _curried(*moreargs, **morekwargs):
        return _curried_func(*(args+moreargs), **dict(kwargs, **morekwargs))
    return _curried


class Neighborhood(threading.Thread):

    def __init__(self, serviceName, serviceType, protocolVersion=1, port=None,
                 serviceRegistrationCallback=None,
                 serviceRegistrationErrorCallback=None,
                 peerServiceDiscoveryCallback=None,
                 peerServiceRemovalCallback=None,
                 peerServiceUpdateCallback=None,
                 peerMessageCallback=None):
        # Ensure the callbacks are valid.
        if not callable(serviceRegistrationCallback):
            raise InvalidCallbackError, "service registration callback"
        if not callable(serviceRegistrationErrorCallback):
            raise InvalidCallbackError, "service registration error callback"
        if not callable(peerServiceDiscoveryCallback):
            raise InvalidCallbackError, "peer service discovery callback"
        if not callable(peerServiceRemovalCallback):
            raise InvalidCallbackError, "peer service removal callback"
        if not callable(peerServiceUpdateCallback):
            raise InvalidCallbackError, "peer service update callback"
        if not callable(peerMessageCallback):
            raise InvalidCallbackError, "peer message callback"

        # TODO: allow port to be None, in which case a free port should be
        # found automatically.

        # Callbacks.
        self.serviceRegistrationCallback      = serviceRegistrationCallback
        self.serviceRegistrationErrorCallback = serviceRegistrationErrorCallback
        self.peerServiceDiscoveryCallback     = peerServiceDiscoveryCallback
        self.peerServiceRemovalCallback       = peerServiceRemovalCallback
        self.peerServiceUpdateCallback        = peerServiceUpdateCallback
        self.peerMessageCallback              = peerMessageCallback
        # Metadata about ourself.
        self.serviceName     = serviceName
        self.serviceType     = serviceType
        self.protocolVersion = protocolVersion
        self.port            = port
        self.txtRecords      = {}
        # Metadata about peers.
        self.peers                                   = {}
        self.peersTxtRecords                         = {}
        self.peersTxtRecordsUpdatedSinceLastCallback = {}
        self.peersTxtRecordsDeletedSinceLastCallback = {}
        # Lock.
        self.lock = threading.Lock()
        # State variables.
        self.serverReady = False
        self.clientReady = False
        self.alive       = True
        self.die         = False
        # Service descriptor references.
        self.sdRefServer           = None # A single sdRef to send messages.
        self.sdRefBrowse           = None # A single sdRef to discover peers.
        self.sdRefSingleShots      = []   # A list of sdRefs that need to return something just once.
        self.sdRefTXTRecordQueries = []   # A list of sdRefs that are "long-lived", always awaiting new/updated TXT records.

        threading.Thread.__init__(self)


    def run(self):
        # Register.
        self._register()

        # Browse.
        self._browse()

        while self.alive:
            # Process responses of the zeroconf server (register, browse,
            # resolve, query callbacks).
            self._processResponses()

            # When registration has been completed:
            if self.serverReady:
                # 1) send multicast messages.
                self._send()

                # 2) receive multicast messages.
                self._receive()

            # Commit suicide when asked to.
            self.lock.acquire()
            if self.die:
                self._commitSuicide()
            self.lock.release()

            # Processing the queues 50 times per second is sufficient.
            time.sleep(0.02)


    def kill(self):
        # Let the thread know it should commit suicide.
        self.lock.acquire()
        self.die = True
        self.lock.release()


    def _register(self):
        """Register the DNS service, along with a primary TXT record, which
        will contain the protocol version.
        Must only be called once.
        """
        primaryTxtRecord = pybonjour.TXTRecord()
        primaryTxtRecord['textvers'] = self.protocolVersion
        self.sdRefServer = pybonjour.DNSServiceRegister(name = self.serviceName,
                                                        regtype = self.serviceType,
                                                        port = self.port,
                                                        txtRecord = primaryTxtRecord,
                                                        callBack = self._serviceRegistrationCallback)


    def _browse(self):
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

        # Only call the peerMessageCallback callback when no more TXT record
        # changes are coming from this service/interface combo.
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
            # Send the callback.
            self.peerMessageCallback(serviceName, interfaceIndex, txtRecords, updated, deleted)


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


    def _serviceRegistrationCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        # Call the appropriate external callback.
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            # Update our own service name.
            self.serviceName = name
            self.serverReady = True
            # Call the service registration callback.
            self.serviceRegistrationCallback(sdRef, flags, errorCode, name, regtype, domain)
        else:
            # Call the error callback, and pass it the error message.
            errorMessage = pybonjour.BonjourError._errmsg[errorCode]
            self.serviceRegistrationErrorCallback(sdRef, flags, errorCode, errorMessage, name, regtype, domain)


    def _send(self):
        # Iterate over all messages in the "out" queue and route them through
        # self._sendMessage(message).
        pass


    def _sendMessage(self, message):
        """Helper method for _send()."""

        newTxtRecords = {}
        for key, value in message.items():
            serializedValue = cPickle.dumps(value)
            # Validate TXT record size: it should never exceed 65536 bytes.
            if len(key) + len('=') + len(serializedValue) > 65536:
                raise MessageTooLargeError, "message size is: %d for key '%s'" % (len(key) + len('=') + len(serializedValue), key)
            txt = pybonjour.TXTRecord({key : serializedValue}, False) # Disable strict checking, which would only allow for 255 bytes.
            newTxtRecords[key] = {'value' : value, 'txtRecord' : txt}

        # Make sets out of the keys of the TXT records to make it easier to
        # determine what should happen.
        curKeys = set(self.txtRecords.keys())
        newKeys = set(newTxtRecords.keys())

        # Update: intersection of current and new TXT records, plus a value
        # comparison to ensure we only update when the value actually changed.
        for key in curKeys.intersection(newKeys):
            if self.txtRecords[key]['value'] != newTxtRecords[key]['value']:
                print "\tUpdating:", key
                pybonjour.DNSServiceUpdateRecord(sdRef = self.sdRefServer,
                                                 RecordRef = self.txtRecords[key]['recordReference'],
                                                 rdata = newTxtRecords[key]['txtRecord'])
                # Update the stored TXT record.
                self.txtRecords[key]['txtRecord'] = newTxtRecords[key]['txtRecord']
                self.txtRecords[key]['value']     = newTxtRecords[key]['value']

        # Remove: difference of current with new TXT records.
        for key in curKeys.difference(newKeys):
            print "\tRemoving: ", key
            # A removed record doesn't get broadcast. So first update the
            # record's value to the string 'DELETE'. This is our way of
            # telling that this TXT record will be deleted.
            pybonjour.DNSServiceUpdateRecord(sdRef = self.sdRefServer,
                                             RecordRef = self.txtRecords[key]['recordReference'],
                                             rdata = pybonjour.TXTRecord({key : 'DELETE'}))
            # Now actually remove the record.
            # TRICKY: this doesn't have to ever happen. See the above comment.
            # pybonjour.DNSServiceRemoveRecord(sdRef = self.sdRefServer,
            #                                  RecordRef = self.txtRecords[key]['recordReference'])
            # Remove the stored TXT record.
            del self.txtRecords[key]

        # Add: difference of new with current TXT records.
        for key in newKeys.difference(curKeys):
            print "\tAdding:", key
            rRef = pybonjour.DNSServiceAddRecord(sdRef = self.sdRefServer,
                                                 rrtype = pybonjour.kDNSServiceType_TXT,
                                                 rdata = newTxtRecords[key]['txtRecord'])
            # Store the new TXT record.
            self.txtRecords[key] = newTxtRecords[key]
            # Also store the record reference.
            self.txtRecords[key]['recordReference'] = rRef


    def _receive(self):
        # - Detect added/updated TXT records using pybonjour.DNSServiceQueryRecord() with kDNSServiceFlagsLongLivedQuery
        # - Compare found TXT records with the stored TXT records.
        pass


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Close the service descriptor references.
        if self.sdRefServer is not None:
            self.sdRefServer.close()
        if self.sdRefBrowse is not None:
            self.sdRefBrowse.close()
        for sdRef in self.sdRefSingleShots:
            sdRef.close()
        for sdRef in self.sdRefTXTRecordQueries:
            sdRef.close()

        # Stop us from running any further.
        self.alive = False




if __name__ == "__main__":
    import time
    import platform
    import copy
    from optparse import OptionParser

    def serviceRegistrationCallback(sdRef, flags, errorCode, name, regtype, domain):
        print "SERVICE REGISTRATION CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, name=%s, regtype=%s, domain=%s" % (sdRef.fileno(), flags, errorCode, name, regtype, domain)

    def serviceRegistrationErrorCallback(sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        print "SERVICE REGISTRATION ERROR CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, errorMessage=%s, name=%s, regtype=%s, domain=%s" % (sdRef, flags, errorCode, errorMessage, name, regtype, domain)

    def peerServiceDiscoveryCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE DISCOVERY CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

    def peerServiceRemovalCallback(serviceName, interfaceIndex):
        print "SERVICE REMOVAL CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d" % (serviceName, interfaceIndex)

    def peerServiceUpdateCallback(serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE UPDATE CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

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

    # Initialize the neighborhood.
    port = 4444
    if options.listenOnly:
        port = 4445
    n = Neighborhood(serviceName = platform.node(),
                     serviceType = '_manyinarow._tcp',
                     protocolVersion = 1,
                     port = port,
                     serviceRegistrationCallback=serviceRegistrationCallback,
                     serviceRegistrationErrorCallback=serviceRegistrationErrorCallback,
                     peerServiceDiscoveryCallback=peerServiceDiscoveryCallback,
                     peerServiceRemovalCallback=peerServiceRemovalCallback,
                     peerServiceUpdateCallback=peerServiceUpdateCallback,
                     peerMessageCallback=peerMessageCallback)

    # Prepare two messages to be broadcast.
    message = {
        'status'           : 'playing',
        'playerName'       : 'Wim',
        'hostedGame'       : "Wim's game",
        'participatedGame' : "Wim's game",
        'players'          : 3,
        'timePlaying'      : 123,
        'newMoves'         : [(3245, 'Brecht', 2), (3246, 'Kristof', 3)],
    }
    messageTwo = copy.deepcopy(message)
    messageTwo['players'] = 2
    del messageTwo['newMoves']

    # Sample usage.
    n.start()
    if not options.listenOnly:
        time.sleep(5)
        n._sendMessage(message)
        time.sleep(2)
        n._sendMessage(messageTwo)
        time.sleep(15)
    else:
        time.sleep(20)
    n.kill()
