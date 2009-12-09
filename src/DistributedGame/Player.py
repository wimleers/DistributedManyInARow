import uuid


class Player(object):
    """Player class, with all three simple properties publicly accessible."""

    def __init__(self, name, UUID = None, color = None):
        self.name  = name

        # Generate a UUID if none is passed in.
        if UUID == None:
            u = uuid.uuid1()
        else:
            u = uuid.UUID(UUID)

        self.UUID  = str(u)

        # Generate a color based on the int representation of the UUID, again
        # if none is passed in.
        if color == None:
            red   = u.int % 255
            green = u.int / 1000 % 255
            blue  = u.int / 1000000 % 255
            self.color = (red, green, blue)
        else:
            self.color = color


    def __str__(self):
        return self.name


    def __eq__(self, other):
        return self.name == other.name and self.UUID == other.UUID and self.color == other.color

    def __ne__(self, other):
        return not self.__eq__(other)
