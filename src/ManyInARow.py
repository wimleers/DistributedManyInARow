import time
from DistributedGame.Game import Game

class ManyInARow(object):

    MOVE, CHAT, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(5)

    def __init__(self, playerName,
                 guiChatCallback,
                 guiJoinedGameCallback,
                 guiPlayerAddCallback, guiPlayerUpdateCallback, guiPlayerRemoveCallback,
                 guiMoveCallback, guiCanMakeMoveCallback,
                 guiWinnerCallback,
                 guiFinishedCallback):
        # Callbacks.
        if not callable(guiChatCallback):
            raise Exception
        if not callable(guiJoinedGameCallback):
            raise Exception
        if not callable(guiPlayerAddCallback):
            raise Exception
        if not callable(guiPlayerUpdateCallback):
            raise Exception
        if not callable(guiPlayerRemoveCallback):
            raise Exception
        if not callable(guiMoveCallback):
            raise Exception
        if not callable(guiCanMakeMoveCallback):
            raise Exception
        if not callable(guiWinnerCallback):
            raise Exception
        if not callable(guiFinishedCallback):
            raise Exception
        
        self.guiChatCallback         = guiChatCallback
        self.guiJoinedGameCallback   = guiJoinedGameCallback
        self.guiPlayerAddCallback    = guiPlayerAddCallback
        self.guiPlayerUpdateCallback = guiPlayerUpdateCallback
        self.guiPlayerRemoveCallback = guiPlayerRemoveCallback
        self.guiMoveCallback         = guiMoveCallback
        self.guiCanMakeMoveCallback  = guiCanMakeMoveCallback
        self.guiWinnerCallback       = guiWinnerCallback
        self.guiFinishedCallback     = guiFinishedCallback

        self.game                          = Game(playerName)
        self.player                        = self.game.player
        self.waitTime                      = None
        self.moveMessage                   = None
        self.numRows                       = None
        self.numCols                       = None
        self.startTime                     = None
        self.winners                       = {}
        self.currentGoal                   = 4
        self.finished                      = False
        self.canMakeMoveAfterMutexAcquired = False
        

    def startGame(self, name, description, numRows, numCols, waitTime):
        # Advertise game.
        self.game.advertise(name, description)

        # Settings for the game.
        self.numRows   = numRows
        self.numCols   = numCols
        self.waitTime  = waitTime
        self.startTime = time.time()

        # Let the GUI know that moves may now be made.
        self._guiCanMakeMove()
        
        
    def joinGame(self, gameUUID):
        # Join the game with the given UUID.
        startTime = self.game.join(gameUUID)

        # Get the settings for the game.
        self.numRows   = self.game.numRows
        self.numCols   = self.game.numCols
        self.waitTime  = self.game.waitTime
        self.startTime = startTime

        # Let the GUI know we successfully joined a game.
        self.guiJoinedGameCallback(self.numRows, self.numCols, self.startTime)

        # Let the GUI know that moves may now be made.        
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


    def _guiCanMakeMove():
        if self.moveMessage is None:
            self.guiCanMakeMoveCallback()
            self.canMakeMoveAfterMutexAcquired = False
        else:
            self.canMakeMoveAfterMutexAcquired = True
        

    def sendChatMessage(self, message):
        self.game.sendMessage({'type' : self.CHAT,'message' : message})


    def messageReceivedCallback(self, playerUUID, message):
        if message['type'] == self.MOVE:
            self.guiMoveCallback(playerUUID, message['col'])
            # Actually make the move.
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
            self.guiPlayerAddCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_UPDATE:
            self.guiPlayerUpdateCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_REMOVE:
            self.guiPlayerRemoveCallback(playerUUID)


    def _isWinnerForXInARow(self, col, goal):
        """Check if the last piece at the given column matched the goal."""
        pass
