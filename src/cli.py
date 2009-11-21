from DistributedGame.Player import Player
from ManyInARowService import ManyInARowService
from ManyInARowGame import ManyInARowGame


def genericCallback(*args):
    print 'CALLBACK, params: ', args

# Create player object that's unique accross the network (universe actually).
player = Player('Jos')
print "Created player %s with color (%d, %d, %d)" % (player.name, player.color[0], player.color[1], player.color[2])

# Start the ManyInARow service.
serviceCallbacks = [genericCallback] * 7
service = ManyInARowService(*serviceCallbacks)
service.start()
