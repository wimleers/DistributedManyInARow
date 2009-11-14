import time
from DistributedGame.Game import Game

class ManyInARow(object):

    MOVE, CHAT, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(5)

    def __init__(self, playerName,
                 guiMoveCallback, guiChatCallback,
                 guiPlayerAddCallback, guiPlayerUpdateCallback, guiPlayerRemoveCallback,
                 guiCanMakeMoveCallback):
        # Callbacks.
        if not callable(guiMoveCallback):
            raise Exception
        if not callable(guiChatCallback):
            raise Exception
        if not callable(guiPlayerAddCallback):
            raise Exception
        if not callable(guiPlayerUpdateCallback):
            raise Exception
        if not callable(guiPlayerRemoveCallback):
            raise Exception
        if not callable(guiCanMakeMoveCallback):
            raise Exception
        self.guiMoveCallback         = guiMoveCallback
        self.guiChatCallback         = guiChatCallback
        self.guiPlayerAddCallback    = guiPlayerAddCallback
        self.guiPlayerUpdateCallback = guiPlayerUpdateCallback
        self.guiPlayerRemoveCallback = guiPlayerRemoveCallback
        self.guiCanMakeMoveCallback  = guiCanMakeMoveCallback

        self.game                          = Game(playerName)
        self.player                        = self.game.player
        self.waitTime                      = None
        self.moveMessage                   = None
        self.numRows                       = None
        self.numCols                       = None
        self.startTime                     = None
        self.winners                       = {}
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
        (startTime, winners) = self.game.join(gameUUID)

        # Get the settings for the game.
        self.numRows   = self.game.numRows
        self.numCols   = self.game.numCols
        self.waitTime  = self.game.waitTime
        self.startTime = startTime
        self.winners   = winners

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
        # @Wim: ik heb paar aanpassinge gedaan aan volgende functies, hope you don't mind (BTW, playerUUID is toch UUID van de player die het bericht naar ons verstuurd heeft eh?)
        if message['type'] == self.MOVE:
            self.guiMoveCallback(playerUUID, message['col'])
        elif message['type'] == self.CHAT:
            self.guiChatCallback(playerUUID, message['message'])
        elif message['type'] == self.PLAYER_ADD:
            self.guiPlayerAddCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_UPDATE:
            self.guiPlayerUpdateCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_REMOVE:
            self.guiPlayerRemoveCallback(playerUUID)
