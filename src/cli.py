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
    print 'CALLBACK, type: "%s", name: "%s", params:' % (type, name), args


# Create player object that's unique accross the network (universe actually).
player = Player('Jos')
print "Created player %s with color (%d, %d, %d)" % (player.name, player.color[0], player.color[1], player.color[2])


# Start the ManyInARow service.
serviceCallbackNames = [
    'guiServiceRegisteredCallback',
    'guiServiceRegistrationFailedCallback',
    'guiServiceUnregisteredCallback',
    'guiPeerServiceDiscoveredCallback',
    'guiPeerServiceRemovedCallback',
    'guiGameAddedCallback',
    'guiGameUpdatedCallback',
    'guiGameEmptyCallback',
]
serviceCallbacks = [curry(genericCallback, 'service', name) for name in serviceCallbackNames]
service = ManyInARowService(*serviceCallbacks)
service.start()


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
# gameCallbacks = [curry(genericCallback, 'game', name) for name in gameCallbackNames]
# game = ManyInARowGame(service, player, *gameCallbacks)
#game.host(name, description, numRows, numCols, waitTime)

time.sleep(2)
service.kill()
