class VectorClockError(Exception): pass
class KeyMismatchError(VectorClockError): pass


class VectorClock(object):

    def __init__(self, vectorClockString=None):
        self.clock = {}
        if vectorClockString is not None:
            self.loads(vectorClockString)


    def add(self, id):
        if id not in self.clock.keys():
            self.clock[id] = 0


    def increment(self, id):
        self.add(id)
        self.clock[id] += 1


    def __repr__(self):
        return self.dumps()


    def dict(self):
        return self.clock


    def dumps(self):
        return ';'.join(['%s:%s' % (id, value) for id, value in self.clock.items()])


    def loads(self, vectorClockString):
        for item in vectorClockString.split(';'):
            (id, value) = item.split(':')
            self.clock[id] = int(value)


    def _mergeKeys(self, other):
        """Add all keys to both vector clocks that are in either one.
        """
        for id in set(other.clock.keys()).difference(set(self.clock.keys())):
            self.clock[id] = 0
        for id in set(self.clock.keys()).difference(set(other.clock.keys())):
            other.clock[id] = 0


    def _binaryOperationCheck(self, other):
        """This helper method is always called before a binary operation."""
        if not isinstance(other, VectorClock):
            raise TypeError("VectorClock can only be compared with VectorClock")
        if not set(self.clock.keys()) == set(other.clock.keys()):
            raise KeyMismatchError


    def __lt__(self, other):
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        for id, value in self.clock.items():
            if value >= other.clock[id]:
                return False
        return True


    def __le__(self, other):
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        for id, value in self.clock.items():
            if value > other.clock[id]:
                return False
        return True


    def __eq__(self, other):
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        return (self is other) or (self.clock == other.clock)


    def __ne__(self, other):
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        return self.clock != other.clock


    def isConcurrentWith(self, other):
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        return not self <= other and not other <= self


    def getSmallerComponents(self, other, minDiff=1):
        """Returns the smaller components in this vector clock, when compared
        with the other vector clock.
        """
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        components = set()
        for id, value in self.clock.items():
            if value <= (other.clock[id] - minDiff):
                components.add(id)
        return components


    def isImmediatelyFollowedBy(self, other):
        """Returns True if and only if the other vector clock contains a
        single id for which the value is 1 more.
        """
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        offsetsOfOne = 0
        for id in self.clock.keys():
            if (self.clock[id] + 1) == other.clock[id]:
                offsetsOfOne += 1
        if offsetsOfOne != 1:
            return False
        else:
            return True


    def isImmediatelyConcurrentWith(self, other):
        """Returns True if a 2 vector clocks are concurrent, but only in 2 ids
        and a difference of 1.
        """
        self._mergeKeys(other)
        return set(self.clock.keys()) == set(other.clock.keys()) and self.isImmediatelyFollowedBy(other) and other.isImmediatelyFollowedBy(self)


    def merge(self, other):
        """In-place merge of both vector clocks."""
        self._mergeKeys(other)
        self._binaryOperationCheck(other)
        for id in self.clock.keys():
            self.clock[id] = max(self.clock[id], other.clock[id])




if __name__ == "__main__":
    v = VectorClock()
    v.increment('bleh')
    v.increment('bwop')
    v.increment('bwop')
    s = str(v)
    print v
    v2 = VectorClock(s)
    print v == v2
    print v != v2
    v2.increment('bleh')
    print v2
