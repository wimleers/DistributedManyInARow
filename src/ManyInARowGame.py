import time
from DistributedGame.Game import Game
from ManyInARow import *
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
                 guiCantMakeMoveCallback,
                 guiWinnerCallback,
                 guiFinishedCallback, guiFreezeCallback,
                 guiUnfreezeCallback):
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
        if not callable(guiCantMakeMoveCallback):
            raise InvalidCallbackError, "guiCantMakeMoveCallback"
        if not callable(guiWinnerCallback):
            raise InvalidCallbackError, "guiWinnerCallback"
        if not callable(guiFinishedCallback):
            raise InvalidCallbackError, "guiFinishedCallback"
        if not callable(guiFreezeCallback):
            raise InvalidCallbackError, "guiFreezeCallback"
        if not callable(guiUnfreezeCallback):
            raise InvalidCallbackError, "guiUnfreezeCallback"
        
        self.guiChatCallback         = guiChatCallback
        self.guiJoinedGameCallback   = guiJoinedGameCallback
        self.guiPlayerJoinedCallback = guiPlayerJoinedCallback
        self.guiPlayerLeftCallback   = guiPlayerLeftCallback
        self.guiMoveCallback         = guiMoveCallback
        self.guiCanMakeMoveCallback  = guiCanMakeMoveCallback
        self.guiCantMakeMoveCallback  = guiCantMakeMoveCallback
        self.guiWinnerCallback       = guiWinnerCallback
        self.guiFinishedCallback     = guiFinishedCallback
        self.guiFreezeCallback       = guiFreezeCallback
        self.guiUnfreezeCallback     = guiUnfreezeCallback

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
        print 'game UUID: ' + str(game.UUID)
        game.messageProcessor.host = game.player.UUID
        game.playing = True


        return game


    @classmethod
    def joinGame(cls, service, player, gameUUID, *gameSettingsAndCallbacks):
        game = cls(service, player, gameUUID, *gameSettingsAndCallbacks)

        # Let the other players in this game now we're joining the game. No
        # confirmation is necessary. Also send the player object because the
        # receiver may not yet have received the Player through the service
        # description via zeroconf.
        game.sendMessage({'type' : game.JOIN, 'player' : game.player, 'originUUID' : game.player.UUID})

        # Also let the service know we've joined the game: this is necessary
        # for the game listing.
        game.service.joinGame(game.UUID)
        game.playing = True

        # Let the GUI know we successfully joined a game (because no join)
        game.guiJoinedGameCallback(game.UUID, game.gameName, game.description, game.numRows, game.numCols, game.waitTime, game.startTime)

        # Let the GUI know that moves may now be made.
        # TODO: the message history must be retrieved completely before the
        # user may start making moves.

        return game


    def makeMove(self, col):
        # if we are the host, we don't need to actually send a message to the host via multicast
        if self.messageProcessor.host == self.player.UUID:
            self.messageProcessor.inbox.put((self.player.UUID, {'type' : self.SERVER_MOVE_TYPE, 'col' : col, 'target' : self.messageProcessor.host,  'timestamp' : time.time() + self.messageProcessor.NTPoffset}))
        # send a move request if we are not the host
        else:
            self.sendMessage({'type' : self.SERVER_MOVE_TYPE, 'col' : col, 'target' : self.messageProcessor.host, 'timestamp' : time.time() + self.messageProcessor.NTPoffset}, False)
        timer = Timer(self.waitTime / 1000, self._guiCanMakeMove)
        timer.start()
        
    def freezeGame(self):
        self.sendMessage({'type' : self.FREEZE})
        
    def unfreezeGame(self):
        self.sendMessage({'type' : self.UNFREEZE})


    def sendHistory(self, playerUUID, minId=0):
        super(ManyInARowGame, self).sendHistory(playerUUID, self.field)


    def _guiCanMakeMove(self):
        if self.moveMessage is None:
            self.guiCanMakeMoveCallback()
            self.canMakeMoveAfterMutexAcquired = False
        else:
            self.canMakeMoveAfterMutexAcquired = True
        
    #checks the current number of players, and disables or enables the gui accordingly
    def checkPlayers(self):
        if len(self.otherPlayers) > 0 and not self.finished:
            self.guiCanMakeMoveCallback()
        else:
            self.guiCantMakeMoveCallback()
        

    def sendChatMessage(self, message):
        self.sendMessage({'type' : self.CHAT, 'message' : message})


    def messageReceivedCallback(self, playerUUID, type, message):
        """This method is called for every message that is received, except
        for mutex messages. Note that all sent messages are also received,
        they can be recognized by the fact that playerUUID == self.player.UUID
        for those messages.
        """
        # if the type is a request for a move, the host checks if it is possible
        # to make a move in this column, and if it is, it sends the move message
        # to all participants
        if type == self.SERVER_MOVE_TYPE:
            row = self._makeMove(playerUUID, message['col'])
            if row != -1:
                self.sendMessage({'type' : self.MOVE, 'row' : row, 'col' : message['col'], 'player' : playerUUID}, False)
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
                
                elif self._boardIsFull():
                    self.guiFinishedCallback(self.winners)
        elif type == self.MOVE:
            row = self._makeMove(message['player'], message['col'], message['row'])
            self.guiMoveCallback(message['player'], message['col'], message['row'])
            # Actually make the move.
            # If this move result in the current goal, we have a winner! We
            # should notify the GUI and mark this game as finished (if no
            # larger "X in a row" is possible) or update the goal.
            if self._isWinnerForXInARow(message['col'], message['row'], self.currentGoal):
                self.winners[self.currentGoal] = message['player']
                self.guiWinnerCallback(self.winners, self.currentGoal)
                # Check if the game is finished or if we should move on to the
                # next goal.
                if self.currentGoal + 1 > max(self.numRows, self.numCols):
                    self.finished = True
                    self.guiFinishedCallback(self.winners)
                else:
                    self.currentGoal += 1
            elif self._boardIsFull():
                self.guiFinishedCallback(self.winners)
        elif type == self.CHAT:
            self.guiChatCallback(playerUUID, message['message'])
        elif type == self.JOIN:              
            if playerUUID != self.player.UUID:                                  
                # Send a HISTORY message containing all the moves in the game          
                self.sendHistory(playerUUID, 0)
                player = message['player']
                self.otherPlayers[playerUUID] = player                 
                self.messageProcessor.players = self.otherPlayers
                self.checkPlayers()
            else:
            # Notify the GUI.            
                player = self.player
            self.guiPlayerJoinedCallback(playerUUID, player)
        elif type == self.WELCOME:
            print 'welcome message!'
            if playerUUID != self.player.UUID:
                player = message['I am']
                print player
                self.otherPlayers[playerUUID] = player  
                self.messageProcessor.players = self.otherPlayers
                self.checkPlayers()
            else:
                player = self.player
            # Notify the GUI.
            self.guiPlayerJoinedCallback(playerUUID, player)
        elif type == self.LEAVE:
            if playerUUID != self.player.UUID:
                if playerUUID in self.otherPlayers:
                    del self.otherPlayers[playerUUID]
                    self.messageProcessor.players = self.otherPlayers
                    self.checkPlayers()
                    self.guiPlayerLeftCallback(playerUUID)
        elif type == self.FREEZE:
            self.guiFreezeCallback()
        elif type == self.UNFREEZE:
            self.guiUnfreezeCallback()


    def _isWinnerForXInARow(self, col, row, goal):
        """Check if the last piece at the given column matched the goal."""
        return self.field.checkWin (col, row, goal)        
        

    def _makeMove(self, playerUUID, col, row = None):
        if row is not None:
            self.field.values[row][col] = playerUUID
        else:
            row = self.field.makeMove (col, playerUUID)
        return row


    def _makeDummyMove (self, col):
        row = self.field.getRowIndexByColumn(col)
        return row
    
    def _makeAiMove(self, players):
        col = self.field.getBestMove(self.player, players, self.currentGoal)
        self.makeMove(col)
        
    def _boardIsFull (self):
        return self.field.isFull()


    def run(self):
        while self.alive:
            # Receive messages and call the appropriate callback.
            with self.lock:
                if self.countReceivedMessages() > 0:
                    (senderUUID, message) = self.receiveMessage()
                    if message['type'] == self.HISTORY_MESSAGE_TYPE:
                        self.processHistoryMessage(senderUUID, message)
                    elif message['type'] == self.MUTEX_MESSAGE_TYPE:
                        self.processMutexMessage(senderUUID, message)
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
