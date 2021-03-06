import copy
import platform
import time

from DistributedGame.Player import Player
from DistributedGame.Service import OneToManyService


class ManyInARowService(OneToManyService):
    """For Many In A Row, the ManyToOne service is a perfect fit. """

    MOVE, CHAT, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(5)

    SERVICE_NAME = platform.node(), # e.g. "WimLeers.local"
    SERVICE_TYPE = '_Many_In_A_Row._tcp'
    SERVICE_PORT = 1337
    SERVICE_PROT = 1

    def __init__(self, player,
                guiServiceRegisteredCallback, guiServiceRegistrationFailedCallback, guiServiceUnregisteredCallback,
                guiPeerServiceDiscoveredCallback, guiPeerServiceRemovedCallback,
                guiPlayerAddedCallback, guiPlayerUpdatedCallback, guiPlayerLeftCallback,
                guiGameAddedCallback, guiGameUpdatedCallback, guiGameEmptyCallback):

        # TRICKY: fix Python screwup.
        self.SERVICE_NAME = self.SERVICE_NAME[0]

        # Call parent constructor with appropriate parameters.
        super(ManyInARowService, self).__init__(self.SERVICE_NAME, self.SERVICE_TYPE, self.SERVICE_PORT, self.SERVICE_PROT)
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
        if not callable(guiPlayerAddedCallback):
            raise InvalidCallbackError, "guiPlayerAddedCallback"
        if not callable(guiPlayerUpdatedCallback):
            raise InvalidCallbackError, "guiPlayerUpdatedCallback"
        if not callable(guiPlayerLeftCallback):
            raise InvalidCallbackError, "guiPlayerLeftCallback"
        if not callable(guiGameAddedCallback):
            raise InvalidCallbackError, "guiGameAddedCallback"
        if not callable(guiGameUpdatedCallback):
            raise InvalidCallbackError, "guiGameUpdatedCallback"
        if not callable(guiGameEmptyCallback):
            raise InvalidCallbackError, "guiGameEmptyCallback"

        self.guiServiceRegisteredCallback         = guiServiceRegisteredCallback
        self.guiServiceRegistrationFailedCallback = guiServiceRegistrationFailedCallback
        self.guiServiceUnregisteredCallback       = guiServiceUnregisteredCallback
        self.guiPeerServiceDiscoveredCallback     = guiPeerServiceDiscoveredCallback
        self.guiPeerServiceRemovedCallback        = guiPeerServiceRemovedCallback
        self.guiPlayerAddedCallback               = guiPlayerAddedCallback
        self.guiPlayerUpdatedCallback             = guiPlayerUpdatedCallback
        self.guiPlayerLeftCallback                = guiPlayerLeftCallback
        self.guiGameAddedCallback                 = guiGameAddedCallback
        self.guiGameUpdatedCallback               = guiGameUpdatedCallback
        self.guiGameEmptyCallback                 = guiGameEmptyCallback

        # Metadata.
        self.player            = player
        self.otherPlayers      = {}
        self.games             = {}
        
        # Broadcast the updated game list.
        self.buildServiceDescription()


    def _serviceRegisteredCallback(self, sdRef, flags, errorCode, name, regtype, domain, port):
        self.guiServiceRegisteredCallback(name, regtype, port)


    def _serviceRegistrationFailedCallback(self, sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        self.guiServiceRegistrationFailedCallback(name, errorCode, errorMessage)


    def _serviceUnregisteredCallback(self, serviceName, serviceType, port):
        self.guiServiceUnregisteredCallback(serviceName, serviceType, port)


    def _peerServiceDiscoveryCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        self.guiPeerServiceDiscoveredCallback(serviceName, interfaceIndex, ip, port)


    def _peerServiceRemovalCallback(self, serviceName, interfaceIndex):
        # Update the player associated with this service, if any.
        if self.otherPlayers.has_key(serviceName):
            player = self.otherPlayers[serviceName]
            del self.otherPlayers[serviceName]
            self.guiPlayerLeftCallback(player)

        self.guiPeerServiceRemovedCallback(serviceName, interfaceIndex)


    def _peerServiceUpdateCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        pass


    def _peerServiceDescriptionUpdatedCallback(self, serviceName, interfaceIndex, txtRecords, updated, deleted):
        description = txtRecords

        # If the service description update contains player information, sync
        # it with our information.
        if description.has_key('player'):
            # Add or update the player object. guiPlayerLeftCallback is called
            # from self._peerServiceRemovalCallback.
            player = Player(description['player']['name'], description['player']['UUID'], description['player']['color'])            
            if not self.otherPlayers.has_key(serviceName):
                self.otherPlayers[serviceName] = player
                self.guiPlayerAddedCallback(player)
            elif self.otherPlayers[serviceName] != player:
                self.otherPlayers[serviceName] = player
                self.guiPlayerUpdatedCallback(self.otherPlayers[serviceName])
            del description['player']

        # Retrieve the player object for this service description update.
        player = self.otherPlayers[serviceName]

        # Now that we've updated the player object, let's look at the games
        # currently going on.
        for gameUUID, game in description.items():
            # Add the game to our list of games when it's not yet included.
            if not self.games.has_key(gameUUID):
                # Only really add it when the broadcaster is participating.
                if game['participating']:
                    self.games[gameUUID] = copy.deepcopy(game)
                    self.games[gameUUID]['players'] = []
                    del self.games[gameUUID]['participating']
                    self.guiGameAddedCallback(gameUUID, self.games[gameUUID])
            else:
                # Update the metadata for the game: either name or description may
                # have changed.
                if game['name'] != self.games[gameUUID]['name'] \
                   or game['description'] != self.games[gameUUID]['description']:
                   game['name']        = self.games[gameUUID]['name']
                   game['description'] = self.games[gameUUID]['description']
                   self.guiGameUpdatedCallback(gameUUID, game)

            # Only update the list of players when the game has been accepted.
            if self.games.has_key(gameUUID):
                # If this player IS PARTICIPATING in this game, but is NOT yet IN
                # OUR LIST of players for the game, ADD him. 
                if game['participating'] and not player.UUID in self.games[gameUUID]['players']:
                    self.games[gameUUID]['players'].append(player.UUID)
                # If this player IS NOT PARTICIPATING in this game, but is IN OUR
                # LIST of players for the game, REMOVE him. 
                elif not game['participating'] and player.UUID in self.games[gameUUID]['players']:
                    self.games[gameUUID]['players'].remove(player.UUID)
                    # If there are no more players in this game, then call the
                    # guiGameEmptyCallback callback, delete it and notify the GUI.
                    if len(self.games[gameUUID]['players']) == 0:
                        self.guiGameEmptyCallback(gameUUID, self.games[gameUUID])
                        del self.games[gameUUID]

        # Detect empty games.
        for gameUUID in self.games.keys():
            if gameUUID not in description.keys():
                self.guiGameEmptyCallback(gameUUID, self.games[gameUUID])
                del self.games[gameUUID]


        # Rebuild the service description now that we've updated our list of
        # games.
        self.buildServiceDescription()


    def buildServiceDescription(self):
        """Build the (zeroconf) service description based on the currently
        available game information."""

        # Build the description.
        # - keys:
        #   * 'player'
        #   * for each game: '<gameUUID>'
        # - values:
        #   * 'player': dict with the following keys: UUID, name, color
        #   * '<gameUUID>': dict with the following keys: name, description,
        #      numRows, numCols, waitTime, startTime, participating
        description = {}
        # 'player'
        description['player'] = {'UUID' : self.player.UUID, 'name' : self.player.name, 'color' : self.player.color}
        # '<gameUUID>'
        games = copy.deepcopy(self.games)
        for gameUUID, game in games.items():
            description[gameUUID] = game
            description[gameUUID]['participating'] = (self.player.UUID in self.games[gameUUID]['players'])
            del description[gameUUID]['players']

        # Broadcast the updated description if it's any different.
        if self.ownServiceDescription != description:
            # Store the new description.
            self.ownServiceDescription = description

            # Set this new description.
            with self.zeroconf.lock:
                self.zeroconf.outbox.put(description)


    def hostGame(self, gameUUID, name, description, numRows, numCols, waitTime, startTime):
        with self.lock:
            # Update the current game list.
            self.games[gameUUID] = {
                'name'        : name,        # 20  characters
                'description' : description, # 100 characters
                'numRows'     : numRows,     # 1-2 characters
                'numCols'     : numCols,     # 1-2 characters
                'waitTime'    : waitTime,    # 1-2 characters
                'starttime'   : startTime,   # 18  charachters
                'players'     : [self.player.UUID], # Not sent with the service description.
            }
            # Broadcast the updated game list.
            self.buildServiceDescription()


    def joinGame(self, gameUUID):
        with self.lock:
            # Update the game list.
            self.games[gameUUID]['players'].append(self.player.UUID)
            # Broadcast the updated game list.
            self.buildServiceDescription()


    def leaveGame(self, gameUUID):
        with self.lock:
            # Update the game list.
            self.games[gameUUID]['players'].remove(self.player.UUID)
            # If there are no more players in this game, then call the
            # guiGameEmptyCallback callback, delete it and notify the GUI.
            if len(self.games[gameUUID]['players']) == 0:
                self.guiGameEmptyCallback(gameUUID, self.games[gameUUID])
                del self.games[gameUUID]
            # Broadcast the updated game list.
            self.buildServiceDescription()


    def stats(self):
        stats = {
            'otherPlayers' : copy.deepcopy(self.otherPlayers),
            'games'        : copy.deepcopy(self.games),
        }
        return stats
