import copy
import Queue
import threading
import uuid

from MessageProcessor import MessageProcessor
from GlobalState import GlobalState
from Player import Player 
import Service


class GameError(Exception): pass
class OneToManyServiceError(GameError): pass
class PlayerError(GameError): pass


class Game(threading.Thread):
    """Wrapper around GlobalState that provides mutual exclusion, which is
    necessary for most (if not all) games."""

    MOVE, CHAT, JOIN, WELCOME, LEAVE, FREEZE, UNFREEZE, NONE= range(8)
    RELEASED, WANTED, HELD = range(3)
    MUTEX_MESSAGE_TYPE = 'MUTEX_MESSAGE'
    HISTORY_MESSAGE_TYPE = 'HISTORY_MESSAGE'


    def __init__(self, service, player, UUID=None):
        # The Service must be a OneToManyService subclass.
        if not isinstance(service, Service.OneToManyService):
            raise OneToManyServiceError
        self.service = service    
        

        # The Player must be a Player instance.
        if not isinstance(player, Player):
            raise PlayerError
        self.player = player
        self.otherPlayers = {}

        # Generate the UUID for this Game when necessary.
        if UUID == None:
            self.UUID = str(uuid.uuid1())
        else:
            self.UUID = UUID
        
        # Thread state variables.
        self.alive = True
        self.die   = False
        self.lock = threading.Condition()
        
        self.messageProcessor = MessageProcessor (service, self.UUID, self.player.UUID)
        self.messageProcessor.start()
        self.SERVER_MOVE_TYPE = self.messageProcessor.SERVER_MOVE_TYPE

        super(Game, self).__init__(name="Game-Thread")
        
    def sendHistory(self, playerUUID, field):
        # only send the history if we are the host
        if self.messageProcessor.host == self.player.UUID:
            players = copy.deepcopy(self.otherPlayers)
            players['host'] = self.player
            moves = []
            
            # append all the moves ever done in the history
            for row in range(field.rows):
                for col in range(field.cols):
                    if field.values[row][col] != -1:
                        moves.append ({'type' : self.MOVE, 'row' : row, 'col' : col, 'player' : field.values[row][col]})
                      
            self.sendMessage({'type' : self.HISTORY_MESSAGE_TYPE, 'players' : players, 'history' : moves, 'target' : playerUUID})
        
    def processHistoryMessage(self, sourceUUID, message):
        if message['target'] == self.player.UUID:
            # add all the players in the gui
            for player in message['players'].keys():
                if player == 'host':
                    self.messageProcessor.host = message['players'][player].UUID
                self.messageProcessor.inbox.put((message['players'][player].UUID, {'type' : self.WELCOME, 'I am' : message['players'][player]}))
            
            # do all the moves done in the past
            for move in message['history']:
                self.messageProcessor.inbox.put((message['players'][player].UUID, {'type' : self.MOVE, 'row' : move['row'], 'col' : move['col'], 'player' : move['player']}))
        
        


    #
    # Game-to-Game messages.
    #
    def sendMessage(self, message, sendToSelf = True):
        print 'Game.sendMesssage:', message
        return self.messageProcessor.sendMessage(message, sendToSelf)


    def countReceivedMessages(self):
        return self.messageProcessor.countReceivedMessages()


    def receiveMessage(self):
        return self.messageProcessor.receiveMessage()
        

    # Thread-related methods.
    #
    def run(self):
        raise NotImplemented


    def kill(self):
        # Let the thread know it should commit suicide.
        with self.lock:
            self.die = True


    def _commitSuicide(self):
        """Commit suicide when asked to. The lock must be acquired before
        calling this method.
        """

        # Kill globalState.
        self.messageProcessor.kill()

        # Stop us from running any further.
        self.alive = False


    #
    # Stats at the time of the function call.
    #
    def stats(self):
        with self.messageProcessor.lock:
            stats = {
                'game UUID' : self.UUID,
                'player UUID' : self.player.UUID,
            }
        return stats
