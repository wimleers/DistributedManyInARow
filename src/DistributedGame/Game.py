import GlobalState

class Game(object):

    RELEASED, WANTED, HELD = range(3)

    def __init__(self):
        self.globalState = GlobalState()
        self.mutexState = self.RELEASED
        pass

    def acquireMutex(self):
        pass

    def releaseMutex(self):
        pass

    def sendMessage(self, message):
        self.globalState.sendMessage(message)
