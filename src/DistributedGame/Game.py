import threading
import uuid


from GlobalState import GlobalState
from Player import Player 
import Service


class GameError(Exception): pass
class OneToManyServiceError(GameError): pass
class PlayerError(GameError): pass


class Game(object):
    """Wrapper around GlobalState that provides mutual exclusion, which is
    necessary for most (if not all) games."""

    RELEASED, WANTED, HELD = range(3)

    def __init__(self, service, player):
        # The Service must be a OneToManyService subclass.
        if not isinstance(service, Service.OneToManyService):
            raise OneToManyServiceError
        self.service = service

        # The Player must be a Player instance.
        if not isinstance(player, Player):
            raise PlayerError
        self.player = player
        self.players = {}

        # Generate the UUID for this Game.
        self.UUID = str(uuid.uuid1())

        # Initialize a Global State.
        self.globalState = GlobalState(service, self.UUID, self.player.UUID)

        # Initialize the mutex state.
        self.mutex = self.RELEASED


    def acquireMutex(self):
        pass


    def releaseMutex(self):
        pass


    def sendMessage(self, message):
        self.globalState.sendMessage(message)
