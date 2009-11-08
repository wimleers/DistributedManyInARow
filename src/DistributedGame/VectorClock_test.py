from VectorClock import *
import unittest


class TestVectorClock(unittest.TestCase):

    def testBasicUsage(self):
        """Test basic usage of VectorClock."""
        v = VectorClock()
        v.add('foo')
        self.assertEqual(v.dict(), {'foo' : 0})

        v.increment('foo')
        v.increment('foo')
        self.assertEqual(v.dict(), {'foo' : 2})

        v.increment('bar')
        self.assertEqual(v.dict(), {'foo' : 2, 'bar' : 1})


    def testSerialization(self):
        """Test serialization/deserialization."""
        v = VectorClock()
        for x in range(10):
            v.increment('foo')
        for x in range(23):
            v.increment('bar')
        # Serialize.
        s = v.dumps()
        # Deserialize.
        v2 = VectorClock(s)
        self.assertEqual(v2.dict(), {'foo' : 10, 'bar' : 23})


    def testComparisons(self):
        """Test all possible comparisons in detail."""
        v1 = VectorClock()
        for x in range(10):
            v1.increment('foo')
        for x in range(5):
            v1.increment('bar')
        for x in range(7):
            v1.increment('baz')
        # v2 is *not* a reference to v1!
        v2 = VectorClock(v1.dumps())

        # "=="
        self.assertTrue (v1 == v2) # True statement.
        self.assertFalse(v1 != v2)
        self.assertTrue (v1 <= v2) # True statement.
        self.assertFalse(v1 <  v2)
        self.assertTrue (v1 >= v2) # True statement.
        self.assertFalse(v1 >  v2)
        self.assertFalse(v1.isConcurrentWith(v2))

        # "<="
        v2.increment('foo')
        self.assertFalse(v1 == v2)
        self.assertTrue (v1 != v2) # True statement.
        self.assertTrue (v1 <= v2) # True statement.
        self.assertFalse(v1 <  v2)
        self.assertFalse(v1 >= v2)
        self.assertFalse(v1 >  v2)
        self.assertFalse(v1.isConcurrentWith(v2))

        # "<"
        v2.increment('bar')
        v2.increment('baz')
        self.assertFalse(v1 == v2)
        self.assertTrue (v1 != v2) # True statement.
        self.assertTrue (v1 <= v2) # True statement.
        self.assertTrue (v1 <  v2) # True statement.
        self.assertFalse(v1 >= v2)
        self.assertFalse(v1 >  v2)
        self.assertFalse(v1.isConcurrentWith(v2))

        # ">=" and ">" don't need to be tested as the same logic for "<=" and
        # "<" is used.

        # Concurrency.
        v1.increment('bar')
        v1.increment('bar')
        # Current situation: v1's bar is at 5+2=7, v2's bar is at 5+1=6, but
        # v2's foo and baz are higher than those of v1.
        self.assertFalse(v1 == v2)
        self.assertTrue (v1 != v2) # True statement.
        self.assertFalse(v1 <= v2)
        self.assertFalse(v1 <  v2)
        self.assertFalse(v1 >= v2)
        self.assertFalse(v1 >  v2)
        self.assertTrue(v1.isConcurrentWith(v2)) # True statement.
        self.assertTrue(v2.isConcurrentWith(v1)) # True statement.

        # List smaller components.
        self.assertEqual(v1.getSmallerComponents(v2), set(['baz', 'foo']))
        self.assertEqual(v2.getSmallerComponents(v1), set(['bar']))

        # List smaller components with a minimum difference of 2.
        self.assertEqual(v2.getSmallerComponents(v1, 2), set([]))
        v1.increment('bar')
        self.assertEqual(v2.getSmallerComponents(v1, 2), set(['bar']))

        # Merge v2 into v1.
        v1.merge(v2)
        self.assertEqual(v1.dict(), {'foo' : 11, 'bar' : 8, 'baz' : 8})


    def testDifferentIds(self):
        """Test binary operations on vector clocks whom contain different ids.
        """

        v1 = VectorClock()
        v1.add('foo')
        v2 = VectorClock()
        v2.increment('bar')

        self.assertFalse(v1 == v2)
        self.assertTrue (v1 != v2) # True statement.
        self.assertTrue (v1 <= v2) # True statement.
        self.assertFalse(v1 <  v2)
        self.assertFalse(v1 >= v2)
        self.assertFalse(v1 >  v2)
        self.assertFalse(v1.isConcurrentWith(v2))

        self.assertFalse(v1 == v2)
        self.assertTrue (v1 != v2) # True statement.
        self.assertTrue (v1 <= v2) # True statement.
        self.assertFalse(v1 <  v2)
        self.assertFalse(v1 >= v2)
        self.assertFalse(v1 >  v2)
        self.assertFalse(v1.isConcurrentWith(v2))
        v1.merge(v2)
        self.assertEqual(v1.dict(), {'foo' : 0, 'bar' : 1})


    def testIsImmediatelyFollowedBy(self):
        """Test the isImmediatelyFollowedBy() method."""
        
        v1 = VectorClock()
        for x in range(10):
            v1.increment('foo')
        for x in range(5):
            v1.increment('bar')
        for x in range(7):
            v1.increment('baz')
        # v2 is *not* a reference to v1!
        v2 = VectorClock(v1.dumps())

        # v2 immediately follows v1.
        v2.increment('bar')
        self.assertTrue(v1.isImmediatelyFollowedBy(v2))
        self.assertFalse(v2.isImmediatelyFollowedBy(v1))

        # v2 still immediately follows v1, even when either vector clock
        # contains a previously unknown value.
        v1.add('pow')


    def testIsImmediatelyConcurrentWith(self):
        """Test the isImmediatelyConcurrentWith() method."""
        
        v1 = VectorClock()
        for x in range(10):
            v1.increment('foo')
        for x in range(5):
            v1.increment('bar')
        for x in range(7):
            v1.increment('baz')
        # v2 is *not* a reference to v1!
        v2 = VectorClock(v1.dumps())

        # Immediate concurrency.
        v1.increment('foo')
        v2.increment('bar')
        self.assertTrue(v1.isImmediatelyConcurrentWith(v2))
        self.assertTrue(v2.isImmediatelyConcurrentWith(v1))

        # Still concurrent, but no longer immediate: the difference for 'foo'
        # is now 2.
        v1.increment('foo')
        self.assertFalse(v1.isImmediatelyConcurrentWith(v2))
        self.assertFalse(v2.isImmediatelyConcurrentWith(v1))

        # Still concurrent, but no longer immediate: the difference is now 1
        # for both 'foo' and 'baz'.
        v2.increment('foo') # Make the concurrency valid again.
        self.assertTrue(v1.isImmediatelyConcurrentWith(v2))
        self.assertTrue(v2.isImmediatelyConcurrentWith(v1))
        v2.increment('baz') # >1 
        self.assertFalse(v1.isImmediatelyConcurrentWith(v2))
        self.assertFalse(v2.isImmediatelyConcurrentWith(v1))

        # Immediate concurrency, although one of the vector clock now contains
        # a new key.
        v1.increment('baz') # Make the concurrency valid again.
        self.assertTrue(v1.isImmediatelyConcurrentWith(v2))
        self.assertTrue(v2.isImmediatelyConcurrentWith(v1))
        v2.add('pow')
        self.assertTrue(v1.isImmediatelyConcurrentWith(v2))
        self.assertTrue(v2.isImmediatelyConcurrentWith(v1))




if __name__ == "__main__":
    unittest.main()
