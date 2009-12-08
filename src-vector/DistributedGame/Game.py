import copy
import Queue
import threading
import uuid


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

        # Initialize a Global State.
        self.globalState = GlobalState(service, self.UUID, self.player.UUID)
        self.globalState.start()

        # Initialize the mutex state.
        self.mutex = self.RELEASED
        self.mutexWantedQueue = Queue.Queue()
        self.agreementReceivedFromPlayers = {}

        # Thread state variables.
        self.alive = True
        self.die   = False
        self.lock = threading.Condition()
        
        self.historyMessages = []

        super(Game, self).__init__(name="Game-Thread")


    #
    # Game-to-Game messages.
    #
    def sendMessage(self, message):
        # print 'Game.sendMesssage:', message
        return self.globalState.sendMessage(message)


    def countReceivedMessages(self):
        return self.globalState.countReceivedMessages()


    def receiveMessage(self):
        return self.globalState.receiveMessage()


    #
    # Service-to-Service messages.
    #
    def sendServiceMessage(self, message):
        with self.service.lock:
            return self.service.sendServiceMessage(message)


    def countReceivedServiceMessages(self):
        return self.service.countReceivedServiceMessages()


    def receiveServiceMessage(self):
        return self.service.receiveServiceMessage()
        
    #
    # History-related methods
    #
        
    def sendHistory (self, playerUUID, minId):
        print self.globalState.clock
        with self.lock:
            with self.globalState.lock:
                if len (self.otherPlayers) == 0 or self.globalState.senderUUID > max (self.otherPlayers):
                    messages = self.globalState.ownMessages(minId, self.globalState.clock.dumps())
                    history = []            
                    # history contains an array of messages that were sent in the past
                    for key in messages.keys():
                        history.append({'hid': messages[key][0], 'tip': messages[key][1], 'senderUUID':messages[key][2], 'originUUID':messages[key][3], 'ownClockValue':messages[key][4], 'clock':messages[key][5], 'message':messages[key][6]})
                        
                    # send the a copy of all the players, since the one who joined the game doesn't
                    # know them yet
                    for p in self.otherPlayers:
                        messages = self.globalState.messagesBySenderUUID(p)
                        for key in messages.keys():
                            history.append({'hid': messages[key][0], 'tip': messages[key][1], 'senderUUID':messages[key][2], 'originUUID':messages[key][3], 'ownClockValue':messages[key][4], 'clock':messages[key][5], 'message':messages[key][6]})
                    
                    print history
                    players = copy.deepcopy(self.otherPlayers)
                    players[self.globalState.senderUUID] = self.player
                    self.sendServiceMessage({'type' : self.HISTORY_MESSAGE_TYPE, 'players' : players, 'targetPlayerUUID' : playerUUID, 'history': history, 'originUUID':self.globalState.senderUUID})
        
    def processHistoryMessage(self, playerUUID, message, messageClock):
        with self.lock:
            with self.globalState.lock:
                if message['targetPlayerUUID'] == self.player.UUID:
                    # add all the players
                    print message
                    for playerUUID in message['players']:
                        self.globalState.inbox.put((playerUUID, {'type': self.WELCOME, 'I am' : message['players'][playerUUID]}, None))
                    # process all messages and ignore mutex requests
                    for m in message['history']:
                        if m['message']['message']['type'] == self.MUTEX_MESSAGE_TYPE:
                            m['message']['message']['type'] = self.NONE
                        self.globalState.waitingRoom[m['clock']] = m['message']
    #
    # Mutex-related methods.
    #

    def acquireMutex(self):
        with self.lock:
            self.mutexRequestedClock = self.globalState.frontier()
            self.mutex = self.WANTED
            for playerUUID in self.otherPlayers.keys():
                self.agreementReceivedFromPlayers[playerUUID] = False
            self.globalState.sendMessage({'type' : self.MUTEX_MESSAGE_TYPE, 'action' : self.WANTED})


    def releaseMutex(self):
        with self.lock:
            self.mutex = self.RELEASED
            while self.mutexWantedQueue.qsize() > 0:
                playerUUID = self.mutexWantedQueue.get()
                # Allow the requester to enter its critical section.
                self.globalState.sendMessage({
                    'type'   : self.MUTEX_MESSAGE_TYPE,
                    'action' : self.RELEASED,
                    'target' : playerUUID
                })


    # TODO: this doesn't work yet when players leave the game while a process
    # is acquiring the mutex...
    def processMutexMessage(self, playerUUID, message, messageClock):
        # Ignore our own messages.
        if playerUUID == self.player.UUID:
            return

        with self.lock:
            # Mutex acquisition request.
            
            print 'mutex request received with action ' + str(message['action'])
            if message['action'] == self.WANTED:
                # If we're acquiring the mutex or have it, queue this mutex
                # acquisition request. Note that we don't have to compare
                # our vector clock with the requester's vector clock because
                # messages are sent on top of GlobalState, which already
                # ensures correct order.
                if self.mutex == self.HELD or (self.mutex == self.WANTED and self.mutexRequestedClock < messageClock):
                    self.mutexWantedQueue.put(playerUUID)
                else:
                    # Allow the requester to enter its critical section.
                    print 'sending mutex released message with target' + str (playerUUID)
                    with self.globalState.lock:
                        self.globalState.sendMessage({
                            'type'   : self.MUTEX_MESSAGE_TYPE,
                            'action' : self.RELEASED,
                            'target' : playerUUID
                        })
            # Mutex acquisition confirmation.
            elif message['action'] == self.RELEASED and message['target'] == self.player.UUID:
                self.agreementReceivedFromPlayers[playerUUID] = True
                # Do we now have permission from all processes to enter the
                # critical section? If yes, call mutexAcquiredCallback.
                agreements = 0
                for key in self.agreementReceivedFromPlayers:
                    if self.agreementReceivedFromPlayers[key]:
                        agreements += 1
                if len(self.agreementReceivedFromPlayers) == agreements:
                    self.mutex = self.HELD
                    self.mutexAcquiredCallback()


    def mutexAcquiredCallback(self):
        # Subclass should implement this.
        raise NotImplemented


    #
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
        self.globalState.kill()

        # Stop us from running any further.
        self.alive = False


    #
    # Stats at the time of the function call.
    #
    def stats(self):
        with self.globalState.lock:
            stats = {
                'clock' : copy.deepcopy(self.globalState.clock),
                'out-of-order messages' : len(self.globalState.waitingRoom),
                'game UUID' : self.UUID,
                'player UUID' : self.player.UUID,
            }
        return stats
