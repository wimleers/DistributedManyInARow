import platform
import time


from DistributedGame.Service import OneToManyService
from DistributedGame.ZeroconfMessaging import ZeroconfMessaging


class ManyInARowService(OneToManyService):
    """For Many In A Row, the ManyToOne service is a perfect fit. """

    MOVE, CHAT, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(5)

    def __init__(self,
                guiServiceRegisteredCallback, guiServiceRegistrationFailedCallback, guiServiceUnregisteredCallback,
                guiPeerServiceDiscoveredCallback, guiPeerServiceRemovedCallback,
                guiGameAddedCallback, guiGameUpdatedCallback, guiGameEmptyCallback):
        # Call parent constructor with appropriate parameters.
        super(ManyInARowService, self).__init__(multicastMessagingClass=ZeroconfMessaging,
                                          serviceName=platform.node(), # e.g. "WimLeers.local"
                                          serviceType='_manyinarow._tcp',
                                          protocolVersion=1,
                                          port=None)
        # Callbacks.
        if not callable(guiServiceRegisteredCallback):
            raise InvalidCallbackError, "guiServiceRegisteredCallback"
        if not callable(guiServiceRegistrationFailedCallback):
            raise InvalidCallbackError, "guiServiceRegistrationFailedCallback"
        if not callable(guiServiceUnregisteredCallback):
            raise InvalidCallbackError, "guiServiceUnregisteredCallback"
        if not callable(guiPeerServiceDiscoveredCallback):
            raise InvalidCallbackError, "guiPeerServiceDiscoveredCallback"
        if not callable(guiPeerServiceRemovedCallback):
            raise InvalidCallbackError, "guiPeerServiceRemovedCallback"

        self.guiServiceRegisteredCallback         = guiServiceRegisteredCallback
        self.guiServiceRegistrationFailedCallback = guiServiceRegistrationFailedCallback
        self.guiServiceUnregisteredCallback       = guiServiceUnregisteredCallback
        self.guiPeerServiceDiscoveredCallback     = guiPeerServiceDiscoveredCallback
        self.guiPeerServiceRemovedCallback        = guiPeerServiceRemovedCallback

        # Maintain a list of active games.
        self.player = None
        self.games  = {}


    def _serviceRegisteredCallback(self, sdRef, flags, errorCode, name, regtype, domain, port):
        self.guiServiceRegisteredCallback(name, regtype, port)


    def _serviceRegistrationFailedCallback(self, sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        self.guiServiceRegistrationFailedCallback(name, errorCode, errorMessage)


    def _serviceUnregisteredCallback(self, serviceName, serviceType, port):
        self.guiServiceUnregisteredCallback(serviceName, serviceType, port)


    def _peerServiceDiscoveryCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        self.guiPeerServiceDiscoveredCallback(serviceName, interfaceIndex, ip, port)


    def _peerServiceRemovalCallback(self, serviceName, interfaceIndex):
        self.guiPeerServiceDiscoveredCallback(serviceName, interfaceIndex)


    def _peerServiceUpdateCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        pass


    def advertiseGame(self, gameUUID, name, description, numRows, numCols, waitTime, startTime, player):
        with self.lock:
            self.player = player
            # Register this game UUID as a destination in the Service.
            self.registerDestination(gameUUID)
            # Update the current game list.
            self.games[gameUUID] = {
                'gameUUID'    : gameUUID,
                'name'        : name,
                'description' : description,
                'numRows'     : numRows,
                'numCols'     : numCols,
                'waitTime'    : waitTime,
                'starttime'   : startTime,
                'players'     : [self.player],    
            }
            # Broadcast the updated game list.
            self.sendServiceMessage(self.games)


    def joinGame(self, gameUUID, player):
        with self.lock:
            self.player = player
            # Register this game UUID as a destination in the Service.
            self.registerDestination(gameUUID)
            # Update the current game list.
            self.games[gameUUID]['players'].append(self.player)
            # Broadcast the updated game list.
            self.sendServiceMessage(self.games)


    def leaveGame(self, gameUUID):
        with self.lock:
            # Remove this game UUID as a destination in the Service.
            self.removeDestination(gameUUID)
            # Update the current game list.
            self.games[gameUUID]['players'].remove(self.player)
            # Broadcast the updated game list.
            self.sendServiceMessage(self.games)


    def _processServiceMessage(self, message):
        # Currently, there's only a single type of service message: those that
        # contain a list of all current games.

        # Get the current games from the message.
        newGames = message
        currentGamesKeys = set(self.games.keys())
        newGamesKeys     = set(newGames.keys())
        # Updated games.
        for gameUUID in currentGamesKeys.intersection(newGamesKeys):
            # Game is empty: no more players.
            if newGames[gameUUID]['players'] == []:
                self.guiGameEmptyCallback(gameUUID)
                del self.games[gameUUID]
            else:
                # Game has been updated: either the name, description
                # or the player list has changed.
                for key, value in self.games[gameUUID]:
                    if newGames[gameUUID][key] != value:
                        self.games[gameUUID] = newGames[gameUUID]
                        self.guiGameUpdatedCallback(**self.games[gameUUID])
                        continue
        # New games.
        for gameUUID in newGamesKeys.difference(currentGamesKeys):
            self.games[gameUUID] = newGames[gameUUID]
            self.guiGameAddedCallback(**self.games[gameUUID])


    def run(self):
        while self.alive:
            # Route incoming messages to the correct destination.
            with self.lock:
                with self.multicast.lock:
                    while self.multicast.inbox.qsize() > 0:
                        packet = self.multicast.inbox.get()
                        for destinationUUID in packet.keys():
                            if self.inbox.has_key(destinationUUID):
                                # Copy the message from the packet to the
                                # inbox with the correct destination.
                                message = packet[destinationUUID]
                                self.inbox[destinationUUID] = message

            # Send outgoing messages.
            with self.lock:
                with self.multicast.lock:
                    while self.outbox.qsize() > 0:
                        # Copy the message from the Service outbox to the
                        # multicast messaging outbox, so that it will be sent.
                        message = self.outbox.get()
                        self.multicast.outbox.put(message)

            # Process service-to-service messages.
            with self.lock:
                if self.inbox[self.SERVICE_TO_SERVICE].qsize() > 0:
                    message = self.inbox[self.SERVICE_TO_SERVICE].get()
                    self._processServiceMessage(message)

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)

        # Kill the underlying MulticastMessaging object.
        self.multicast.kill()
