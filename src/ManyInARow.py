from DistributedGame.Game import Game

class ManyInARow(object):

    MOVE, CHAT, PLAYER_ADD, PLAYER_UPDATE, PLAYER_REMOVE = range(5)

    def __init__(self, playerName,
                 waitTime,
                 guiMoveCallback, guiChatCallback,
                 guiPlayerAddCallback, guiPlayerUpdateCallback, guiPlayerRemoveCallback,
                 guiCanMakeMoveCallback):
        self.game = Game(playerName)
        self.player = self.game.player

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

        self.waitTime = waitTime
        self.moveMessage = None
        self.canMakeMoveAfterMutexAcquired = False
        self._guiCanMakeMove()
        
    def makeMove(self, col):
        self.moveMessage = {'type' : self.MOVE, 'col' : col}
        self.game.acquireMutex(self.mutexAcquiredCallback)
        timer = Timer(self.waitTime, self._guiCanMakeMove)
        timer.start()


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
            self.guiMoveCallback(message['col'])
        elif message['type'] == self.CHAT:
            self.guiChatCallback(playerUUID, message['message'])
        elif message['type'] == self.PLAYER_ADD:
            self.guiPlayerAddCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_UPDATE:
            self.guiPlayerUpdateCallback(playerUUID, message['player'])
        elif message['type'] == self.PLAYER_REMOVE:
            self.guiPlayerRemoveCallback(playerUUID)
