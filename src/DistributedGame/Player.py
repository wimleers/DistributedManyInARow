import uuid


class Player(object):
    """Player class, with all three simple properties publicly accessible."""

    def __init__(self, name):
        self.name  = name

        # Generate a UUID.
        self.UUID  = str(uuid.uuid1())

        # Generate a color based on the hash of the UUID.
        red   = hash(self.UUID) % 255
        green = hash(self.UUID) / 1000 % 255
        blue  = hash(self.UUID) / 1000000 % 255
        self.color = (red, green, blue)


    def __str__(self):
        return self.name
