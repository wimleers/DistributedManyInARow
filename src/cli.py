from optparse import OptionParser
import time

from DistributedGame.Player import Player
from ManyInARowService import ManyInARowService
from ManyInARowGame import ManyInARowGame


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




parser = OptionParser()
parser.add_option("-l", "--listenOnly", action="store_true", dest="listenOnly",
                  help="listen only (don't broadcast)")
(options, args) = parser.parse_args()
if options.listenOnly:
    playerName = 'Listener'
else:
    playerName = 'Jos'




# Create player object that's unique accross the network (universe actually).
player = Player(playerName)
print "[CLI] Created player %s with color (%d, %d, %d)." % (player.name, player.color[0], player.color[1], player.color[2])


# Start the ManyInARow service.
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
service = ManyInARowService(player, *serviceCallbacks)
service.start()
print "[CLI] Started ManyInARowService."

# In the real implementation, don't sleep but wait for the
# guiServiceRegisteredCallback callback.
time.sleep(1.5)

# Start a ManyInARow game.
gameCallbackNames = [
    'guiChatCallback',
    'guiJoinedGameCallback',
    'guiPlayerAddCallback',
    'guiPlayerUpdateCallback',
    'guiPlayerRemoveCallback',
    'guiMoveCallback',
    'guiCanMakeMoveCallback',
    'guiWinnerCallback',
    'guiFinishedCallback',
]
gameCallbacks = [curry(genericCallback, 'GAME', name) for name in gameCallbackNames]
game = ManyInARowGame(service, player, *gameCallbacks)
print "[CLI] Started ManyInARowGame."

if not options.listenOnly:
    print "[CLI] Hosting game 'Ubergame'."
    gameSettings = {
        'name'        : 'Ubergame',
        'description' : 'Zis is dah ubergame!',
        'numRows'     : 10,
        'numCols'     : 12,
        'waitTime'    : 3,
    }
    game.host(**gameSettings)
    time.sleep(0.5)

    print "[CLI] Sending chat message."
    game.sendChatMessage("Guten tag, anybody around?")
    time.sleep(0.5)
else:
    time.sleep(5)

print "[CLI] Leaving the game 'Ubergame'."
del game
time.sleep(0.5)

print "[CLI] Stopping the ManyInARowService."
service.kill()
time.sleep(0.5)
