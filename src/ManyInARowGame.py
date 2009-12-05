import time
from DistributedGame.Game import Game
from vieropeenrij import *
from threading import Timer


class ManyInARowGameError(Exception): pass
class InvalidCallbackError(ManyInARowGameError): pass
class OneToManyServiceError(ManyInARowGameError): pass


class ManyInARowGame(Game):


    def __init__(self, service, player, UUID,
                 name, description, numRows, numCols, waitTime,
                 guiChatCallback,
                 guiJoinedGameCallback,
                 guiPlayerJoinedCallback, guiPlayerLeftCallback,
                 guiMoveCallback, guiCanMakeMoveCallback,
                 guiWinnerCallback,
                 guiFinishedCallback):
        super(ManyInARowGame, self).__init__(service, player, UUID)

        # Callbacks.
        if not callable(guiChatCallback):
            raise InvalidCallbackError, "guiChatCallback"
        if not callable(guiJoinedGameCallback):
            raise InvalidCallbackError, "guiJoinedGameCallback"
        if not callable(guiPlayerJoinedCallback):
            raise InvalidCallbackError, "guiPlayerJoinedCallback"
        if not callable(guiPlayerLeftCallback):
            raise InvalidCallbackError, "guiPlayerLeftCallback"
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
        self.guiPlayerJoinedCallback = guiPlayerJoinedCallback
        self.guiPlayerLeftCallback   = guiPlayerLeftCallback
        self.guiMoveCallback         = guiMoveCallback
        self.guiCanMakeMoveCallback  = guiCanMakeMoveCallback
        self.guiWinnerCallback       = guiWinnerCallback
        self.guiFinishedCallback     = guiFinishedCallback

        # Game settings
        self.gameName    = name
        self.description = description
        self.numRows     = numRows
        self.numCols     = numCols
        self.waitTime    = waitTime
        self.startTime   = time.time()

        # Game field.
        self.field = Field(numRows, numCols)

        # Game state.
        self.moveMessage                   = None
        self.winners                       = {}
        self.currentGoal                   = 4 # 4 is always the initial goal
        self.finished                      = False
        self.canMakeMoveAfterMutexAcquired = False

        # Notify the GUI.
        self.guiPlayerJoinedCallback(player.UUID, player)


    @classmethod
    def hostGame(cls, service, player, *gameSettingsAndCallbacks):
        game = cls(service, player, None, *gameSettingsAndCallbacks)

        # Let the service know we're hosting a game, so it can be advertised.
        game.service.hostGame(game.UUID,
                              game.gameName, game.description,
                              game.numRows, game.numCols,
                              game.waitTime, game.startTime)
        game.playing = True

        # Let the GUI know that moves may now be made.
        game._guiCanMakeMove()

        return game


    @classmethod
    def joinGame(cls, service, player, gameUUID, *gameSettingsAndCallbacks):
        game = cls(service, player, gameUUID, *gameSettingsAndCallbacks)

        # Let the other players in this game now we're joining the game. No
        # confirmation is necessary. Also send the player object because the
        # receiver may not yet have received the Player through the service
        # description via zeroconf.
        game.sendMessage({'type' : game.JOIN, 'player' : game.player})

        # Also let the service know we've joined the game: this is necessary
        # for the game listing.
        game.service.joinGame(game.UUID)
        game.playing = True

        # Let the GUI know we successfully joined a game (because no join)
        game.guiJoinedGameCallback(game.UUID, game.gameName, game.description, game.numRows, game.numCols, game.waitTime, game.startTime)

        # Let the GUI know that moves may now be made.
        # TODO: the message history must be retrieved completely before the
        # user may start making moves.
        game._guiCanMakeMove()

        return game


    def makeMove(self, col):
        self.moveMessage = {'type' : self.MOVE, 'col' : col}
        self.acquireMutex()
        timer = Timer(self.waitTime, self._guiCanMakeMove)
        timer.start()


    def sendHistory(self, playerUUID, minId=0):
        super(ManyInARowGame, self).sendHistory(playerUUID, minId)


    def mutexAcquiredCallback(self):
        self.sendMessage(self.moveMessage)
        self.moveMessage = None
        self.releaseMutex()
        if self.canMakeMoveAfterMutexAcquired:
            self._guiCanMakeMove()


    def _guiCanMakeMove(self):
        if self.moveMessage is None:
            self.guiCanMakeMoveCallback()
            self.canMakeMoveAfterMutexAcquired = False
        else:
            self.canMakeMoveAfterMutexAcquired = True
        

    def sendChatMessage(self, message):
        self.sendMessage({'type' : self.CHAT, 'message' : message})


    def messageReceivedCallback(self, playerUUID, type, message):
        """This method is called for every message that is received, except
        for mutex messages. Note that all sent messages are also received,
        they can be recognized by the fact that playerUUID == self.player.UUID
        for those messages.
        """

        if type == self.MOVE:
            row = self._makeMove(playerUUID, message['col'])
            self.guiMoveCallback(playerUUID, message['col'], row)
            # Actually make the move.
            # If this move result in the current goal, we have a winner! We
            # should notify the GUI and mark this game as finished (if no
            # larger "X in a row" is possible) or update the goal.
            if self._isWinnerForXInARow(message['col'], row, self.currentGoal):
                self.winners[self.currentGoal] = playerUUID
                self.guiWinnerCallback(self.winners, self.currentGoal)
                # Check if the game is finished or if we should move on to the
                # next goal.
                if self.currentGoal + 1 > max(self.numRows, self.numCols):
                    self.finished = True
                    self.guiFinishedCallback(self.winners)
                else:
                    self.currentGoal += 1
        elif type == self.CHAT:
            self.guiChatCallback(playerUUID, message['message'])
        elif type == self.JOIN:
            if playerUUID != self.player.UUID:
                player = message['player']
                self.otherPlayers[playerUUID] = player                      
                # Send a HISTORY message containing all the moves this player did                
                self.sendHistory(playerUUID, 0)
                # Send a WELCOME message as a reply, to let the player who joined
                # get to know all players
                self.sendMessage({'type' : self.WELCOME, 'I am' : self.player})  
            else:
                player = self.player
            # Notify the GUI.
            self.guiPlayerJoinedCallback(playerUUID, player)
        elif type == self.WELCOME:
            if playerUUID != self.player.UUID:
                player = message['I am']
                self.otherPlayers[playerUUID] = player
            else:
                player = self.player
            # Notify the GUI.
            self.guiPlayerJoinedCallback(playerUUID, player)
        elif type == self.LEAVE:
            if playerUUID != self.player.UUID:
                del self.otherPlayers[playerUUID]
                self.guiPlayerLeftCallback(playerUUID)


    def _isWinnerForXInARow(self, col, row, goal):
        """Check if the last piece at the given column matched the goal."""
        return self.field.checkWin (col, row, goal)        
        

    def _makeMove(self, playerUUID, col):
        row = self.field.makeMove (col, playerUUID)
        return row


    def _makeDummyMove (self, col):
        row = self.field.getRowIndexByColumn(col)
        return row


    def run(self):
        while self.alive:
            # Receive messages and call the appropriate callback.
            with self.lock:
                if self.countReceivedMessages() > 0:
                    (senderUUID, message, messageClock) = self.receiveMessage()   
                    if message['type'] == self.HISTORY_MESSAGE_TYPE:
                        self.processHistoryMessage(senderUUID, message, messageClock)
                    elif message['type'] == self.MUTEX_MESSAGE_TYPE:
                        self.processMutexMessage(senderUUID, message, messageClock)
                    else:
                        self.messageReceivedCallback(senderUUID, message['type'], message)            

            # Commit suicide when asked to.
            with self.lock:
                if self.die:
                    self._commitSuicide()

            # 20 refreshes per second is plenty.
            time.sleep(0.05)


    def kill(self):
        # Let the other players in this game now we're leaving the game.
        self.sendMessage({'type' : self.LEAVE})
        # Ensure the Service is aware of this as well, so the service
        # description can be updated.
        self.service.leaveGame(self.UUID)

        super(ManyInARowGame, self).kill()
