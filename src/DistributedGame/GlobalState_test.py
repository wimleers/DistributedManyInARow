from History import *
import os
import os.path
import unittest


class TestHistory(unittest.TestCase):

    def setUp(self):
        # Ensure that every test suite runs on a fresh new database.
        dbFile = './testHistory.sqlite'
        if os.path.exists(dbFile):
            os.remove(dbFile)
        self.history = History(dbFile)


    def testInitialDB(self):
        """The initial database should have no groups."""
        self.assertEqual(self.storage.groups(), [])


    def testSingleGrid(self):
        """Store a single grid and retrieve all its metadata."""
        # Create simple entry in the database.
        group = "Het Zwin"
        name  = "Toestand 1980"
        grid  = [[1,2,3],
                 [4,5,6],
                 [7,8,9]]
        sources = [(0,0),(0,1)]
        targets = [(1,2),(2,2)]
        id = self.storage.storeGrid(group, name, grid, sources, targets)

        # Validate.
        self.assertEqual(id, 1)
        self.assertEqual(self.storage.groups(), ['Het Zwin'])
        self.assertEqual(self.storage.gridsInGroup('Het Zwin'), {1 : 'Toestand 1980'})
        self.assertEqual(self.storage.grid(1), (grid, sources, targets))


    def testEverything(self):
        """Store a group of grids, along with result grids of multiple types,
        retrieve all its metadata and then delete it all.
        """

        # Create simple entry in the database.
        group = "Het Zwin"
        name  = "Toestand 1980"
        grid  = [[1,2,3],
                 [4,5,6],
                 [7,8,9]]
        sources = [(0,0),(0,1)]
        targets = [(1,2),(2,2)]
        id = self.storage.storeGrid(group, name, grid, sources, targets)

        # Validate.
        self.assertEqual(id, 1)
        self.assertEqual(self.storage.groups(), ['Het Zwin'])
        self.assertEqual(self.storage.gridsInGroup('Het Zwin'), {1 : 'Toestand 1980'})
        self.assertEqual(self.storage.grid(1), (grid, sources, targets))


if __name__ == "__main__":
    unittest.main()
