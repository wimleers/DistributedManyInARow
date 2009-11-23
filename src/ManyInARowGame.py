import time
from DistributedGame.Game import Game


class ManyInARowGameError(Exception): pass
class InvalidCallbackError(ManyInARowGameError): pass
class OneToManyServiceError(ManyInARowGameError): pass


class ManyInARowGame(object):

    MOVE, CHAT, JOIN, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(6)

    def __init__(self, service, player,
                 guiChatCallback,
                 guiJoinedGameCallback,
                 guiPlayerAddCallback, guiPlayerUpdateCallback, guiPlayerRemoveCallback,
                 guiMoveCallback, guiCanMakeMoveCallback,
                 guiWinnerCallback,
                 guiFinishedCallback):

        # Callbacks.
        if not callable(guiChatCallback):
            raise InvalidCallbackError, "guiChatCallback"
        if not callable(guiJoinedGameCallback):
            raise InvalidCallbackError, "guiJoinedGameCallback"
        if not callable(guiPlayerAddCallback):
            raise InvalidCallbackError, "guiPlayerAddCallback"
        if not callable(guiPlayerUpdateCallback):
            raise InvalidCallbackError, "guiPlayerUpdateCallback"
        if not callable(guiPlayerRemoveCallback):
            raise InvalidCallbackError, "guiPlayerRemoveCallback"
        if not callable(guiMoveCallback):
            raise InvalidCallbackError, "guiMoveCallback"
        if not callable(guiCanMakeMoveCallback):
            raise InvalidCallbackError, "guiCanMakeMoveCallback"
        if not callable(guiWinnerCallback):
            raise InvalidCallbackError, "guiWinnerCallback"
        if not callable(guiFinishedCallback):
            raise InvalidCallbackError, "guiFinishedCallback"
        
        self.guiChatCallback         = guiChatCallback
        self.guiJoinedGameCallback   = guiJoinedGameCallback
        self.guiPlayerAddCallback    = guiPlayerAddCallback
        self.guiPlayerUpdateCallback = guiPlayerUpdateCallback
        self.guiPlayerRemoveCallback = guiPlayerRemoveCallback
        self.guiMoveCallback         = guiMoveCallback
        self.guiCanMakeMoveCallback  = guiCanMakeMoveCallback
        self.guiWinnerCallback       = guiWinnerCallback
        self.guiFinishedCallback     = guiFinishedCallback

        # Game settings
        self.name        = None
        self.description = None
        self.numRows     = None
        self.numCols     = None
        self.waitTime    = None
        self.startTime   = None        

        # Game state.
        self.moveMessage                   = None
        self.winners                       = {}
        self.currentGoal                   = 4
        self.finished                      = False
        self.canMakeMoveAfterMutexAcquired = False
        self.playing                       = False

        # Create the underlying distributed game and pass it the Player object.
        self.service = service
        self.player  = player
        self.game    = Game(self.service, self.player)


    def __del__(self):
        if self.playing:
            self.service.leaveGame(self.game.UUID)


    def host(self, name, description, numRows, numCols, waitTime):
        # Store the game settings.
        self.name        = name
        self.description = description
        self.numRows     = numRows
        self.numCols     = numCols
        self.waitTime    = waitTime
        self.startTime   = time.time()

        # Advertise the game.
        self.service.advertiseGame(self.game.UUID,
                                   self.name, self.description,
                                   self.numRows, self.numCols,
                                   self.waitTime, self.startTime,
                                   self.player)
        self.playing = True

        # Let the GUI know that moves may now be made.
        self._guiCanMakeMove()
        
        
    def join(self, gameUUID):
        # Update the UUID of the DistributedGame.Game that was created.
        self.game.UUID = gameUUID

        # Store the game settings.
        game = self.service.games[gameUUID]
        self.name        = game['name']
        self.description = game['description']
        self.numRows     = game['numRows']
        self.numCols     = game['numCols']
        self.waitTime    = game['waitTime']
        self.startTime   = game['startTime']

        # Let the other players in this game now we're joining the game. No
        # confirmation is necessary.
        self.game.sendMessage({'type' : self.JOIN, 'player' : self.player})

        # Also let the service know we've joined the game: this is necessary
        # for the game listing.
        self.service.joinGame(gameUUID, self.player)
        self.playing = True

        # Let the GUI know we successfully joined a game (because no join)
        self.guiJoinedGameCallback(self.name, self.description, self.numRows, self.numCols, self.waitTime, self.startTime)

        # Let the GUI know that moves may now be made.
        # TODO: the message history must be retrieved completely before the
        # user may start making moves.
        self._guiCanMakeMove()


    def makeMove(self, col):
        self.moveMessage = {'type' : self.MOVE, 'col' : col}
        self.game.acquireMutex(self.mutexAcquiredCallback)
        timer = Timer(self.waitTime, self._guiCanMakeMove)
        timer.start()


    def getHistory(self, minId=0):
        return self.game.getHistory(minId)


    def mutexAcquiredCallback(self):
        self.game.sendMessage(self.moveMessage)
        self.moveMessage = None
        self.game.releaseMutex()
        if self.canMakeMoveAfterMutexAcquired:
            self._guiCanMakeMove()


    def _guiCanMakeMove(self):
        if self.moveMessage is None:
            self.guiCanMakeMoveCallback()
            self.canMakeMoveAfterMutexAcquired = False
        else:
            self.canMakeMoveAfterMutexAcquired = True
        

    def sendChatMessage(self, message):
        self.game.sendMessage({'type' : self.CHAT, 'message' : message})


    def messageReceivedCallback(self, playerUUID, message):
        if message['type'] == self.MOVE:
            self.guiMoveCallback(playerUUID, message['col'])
            # Actually make the move.
            #@wim: de GUI zou eigenlijk een row en een col moeten meekrijgen, anders weet ik niet hoe hoog die moet staan
            self._makeMove(playerUUID, message['col'])
            # If this move result in the current goal, we have a winner! We
            # should notify the GUI and mark this game as finished (if no
            # larger "X in a row" is possible) or update the goal.
            if self._isWinnerForXInARow(message['col'], self.currentGoal):
                self.winners[self.currentGoal] = playerUUID
                self.guiWinnerCallback(self.winners, self.currentGoal)
                # Check if the game is finished or if we should move on to the
                # next goal.
                if self.currentGoal + 1 > max(self.numRows, self.numCols):
                    self.finished = True
                    self.guiFinishedCallback(self.winners)
                else:
                    self.currentGoal += 1
        elif message['type'] == self.CHAT:
            self.guiChatCallback(playerUUID, message['message'])
        elif message['type'] == self.PLAYER_ADD:
            player = message['player']
            self.game.players[playerUUID] = player
            self.guiPlayerAddCallback(playerUUID, player)
        elif message['type'] == self.PLAYER_UPDATE:
            player = message['player']
            self.game.players[playerUUID] = player
            self.guiPlayerUpdateCallback(player.UUID, player)
        elif message['type'] == self.PLAYER_REMOVE:
            player = message['player']
            del self.game.players[playerUUID]
            self.guiPlayerRemoveCallback(player.UUID)


    def _isWinnerForXInARow(self, col, goal):
        """Check if the last piece at the given column matched the goal."""
        pass
