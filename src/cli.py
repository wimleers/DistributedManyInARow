from optparse import OptionParser
import time

from DistributedGame.Player import Player
from ManyInARowService import ManyInARowService
from ManyInARowGame import ManyInARowGame


parser = OptionParser()
parser.add_option("-l", "--listenOnly", action="store_true", dest="listenOnly",
                  help="listen only (don't broadcast)")
(options, args) = parser.parse_args()
if options.listenOnly:
    playerName = 'Listener'
else:
    playerName = 'Jos'


# Copied from django.utils.functional
def curry(_curried_func, *args, **kwargs):
    def _curried(*moreargs, **morekwargs):
        return _curried_func(*(args+moreargs), **dict(kwargs, **morekwargs))
    return _curried


def genericCallback(type, name, *args):
    print '\tCALLBACK \n\
           \ttype: "%s" \n\
           \tcallback name: "%s" \n\
           \tparams:' % (type, name), args

serviceCallbackNames = [
   'guiServiceRegisteredCallback',
   'guiServiceRegistrationFailedCallback',
   'guiServiceUnregisteredCallback',
   'guiPeerServiceDiscoveredCallback',
   'guiPeerServiceRemovedCallback',
   'guiPlayerAddedCallback',
   'guiPlayerUpdatedCallback',
   'guiPlayerLeftCallback',
   'guiGameAddedCallback',
   'guiGameUpdatedCallback',
   'guiGameEmptyCallback',
]
serviceCallbacks = [curry(genericCallback, 'SERVICE', name) for name in serviceCallbackNames]
gameCallbackNames = [
    'guiChatCallback',
    'guiJoinedGameCallback',
    'guiPlayerJoinedCallback',
    'guiPlayerLeftCallback',
    'guiMoveCallback',
    'guiCanMakeMoveCallback',
    'guiCantMakeMoveCallback',
    'guiWinnerCallback',
    'guiFinishedCallback',
    'guiFreezeCallback',
    'guiUnfreezeCallback',
]
gameCallbacks = [curry(genericCallback, 'GAME', name) for name in gameCallbackNames]
game = object()

def guiGameAddedCallback(gameUUID, gameSettings):
    genericCallback('GAME', 'guiGameAddedCallback', gameUUID, gameSettings)
    print "[CLI] joining the game %s with UUID %s" % (gameSettings['name'], gameUUID)
    global game
    game = ManyInARowGame.joinGame(service, player, gameUUID,
                               gameSettings['name'], gameSettings['description'], gameSettings['numRows'], gameSettings['numCols'], gameSettings['waitTime'],
                               *gameCallbacks)
    game.start()





# Create player object that's unique accross the network (universe actually).
player = Player(playerName)
print "[CLI] Created player %s with color (%d, %d, %d)." % (player.name, player.color[0], player.color[1], player.color[2])


# Start the ManyInARow service.
if options.listenOnly:
    # When listening, join the game created by the non-listener.
    index = serviceCallbackNames.index('guiGameAddedCallback')
    serviceCallbacks[index] = guiGameAddedCallback
service = ManyInARowService(player, *serviceCallbacks)
service.start()
print "[CLI] Started ManyInARowService."

# In the real implementation, don't sleep but wait for the
# guiServiceRegisteredCallback callback.
time.sleep(1.5)


# Start a ManyInARow game.
name        = 'Ubergame'
description = 'Zis is dah ubergame!'
numRows     = 10
numCols     = 12
waitTime    = 3

if not options.listenOnly:
    print "[CLI] Hosting ManyInARowGame 'Ubergame'."
    game = ManyInARowGame.hostGame(service, player, name, description, numRows, numCols, waitTime, *gameCallbacks)
    game.start()
    time.sleep(2)

    print "[CLI] Sending chat message."
    game.sendChatMessage("Guten tag, anybody around?")
    time.sleep(0.5)

    print "[CLI] Making a move."
    game.makeMove(2)
    time.sleep(0.5)
else:
    time.sleep(2)

time.sleep(5)

if not hasattr(game, 'stats'):
    print '[CLI] No game found: could not join any game.'
    exit(1)

print "[CLI] Game stats:"
print game.stats()

# Let the listener wait for Jos to leave.
if options.listenOnly:
    time.sleep(10)
print "[CLI] Leaving the game 'Ubergame'."
game.kill()
time.sleep(0.5)

print "[CLI] Service stats:"
print service.stats()

print "[CLI] Stopping the ManyInARowService."
service.kill()
time.sleep(0.5)
