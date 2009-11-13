import uuid


class Player(object):
    """Player class, with all three simple properties publicly accessible."""

    def __init__(self, name):
        self.name  = name

        # Generate a UUID.
        u = uuid.uuid1()
        self.UUID  = str(u)

        # Generate a color based on the int representation of the UUID.
        red   = u.int % 255
        green = u.int / 1000 % 255
        blue  = u.int / 1000000 % 255
        self.color = (red, green, blue)


    def __str__(self):
        return self.name
