from vieropeenrij import *
import unittest

class TestVierOpEenRij(unittest.TestCase):
    def runTest(self):
        self.playersTest()
        self.fieldTest(Field (10, 15))
        self.fieldTest(Field (15, 10))
        self.fieldTest(Field (10, 10))

    #unit test for the Players class
    def playersTest(self):
   
        players = Players()
        #add some players
        players.addPlayer (Player('Kristof', 'red'))
        players.addPlayer (Player('Brecht', 'blue'))
        players.addPlayer (Player('Wim', 'pink'))
        
        #keep getting the next player and check if the names are updated correctly
        self.assertEquals (players.getCurrentPlayerName() , 'Kristof')
        players.getNextPlayer()
        self.assertEquals (players.getCurrentPlayerName() , 'Brecht')
        players.getNextPlayer()
        self.assertEquals (players.getCurrentPlayerName() , 'Wim')
        players.getNextPlayer()
        self.assertEquals (players.getCurrentPlayerName() , 'Kristof')
        players.getNextPlayer()

        #delete a player and check if the correct player gets the next turn
        players.deletePlayer (Player('Brecht', 'blue'))
        self.assertEquals (players.getCurrentPlayerName() , 'Wim')

    #unit test for the Field class
    def fieldTest(self, field):
        #keep doing moves at the same column and check if the returned value is correct
        for i in range (1, 13):
            self.assertEquals (field.makeMove (1, 1) , max(field.rows - i, -1))

        #check if the checkWin function correctly detects the vertical 4 in a row
        self.assertEquals (field.checkWin (1, 5, 4) , True)
        self.assertEquals (field.checkWin (1, 5, 14) , False)

        #check if a horizontal 4 in a row is detected
        field.makeMove (3,2)
        field.makeMove (4,2)
        field.makeMove (5,2)
        field.makeMove (6,2)
        self.assertEquals (field.checkWin (3, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (4, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (5, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (6, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (7, field.rows-1, 4), False)

        #check if a diagonal (left bottom to top right) 4 in a row is detected
        field.makeMove (2, 1)
        field.makeMove (3, 1)
        field.makeMove (4, 1)
        field.makeMove (4, 1)
        field.makeMove (5, 1)
        field.makeMove (5, 1)
        field.makeMove (5, 1)   
        self.assertEquals (field.checkWin (2, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (3, field.rows-2, 4), True)
        self.assertEquals (field.checkWin (4, field.rows-3, 4), True)
        self.assertEquals (field.checkWin (5, field.rows-4, 4), True)
        self.assertEquals (field.checkWin (7, field.rows-1, 4), False)     

        #check if a diagonal (top left to bottom right) 4 in a row is detected
        field.makeMove (9, 3)
        field.makeMove (8, 3)
        field.makeMove (8, 3)
        field.makeMove (7, 3)
        field.makeMove (7, 3)
        field.makeMove (7, 3)
        field.makeMove (6, 3)   
        field.makeMove (6, 3)
        field.makeMove (6, 3)
        self.assertEquals (field.checkWin (9, field.rows-1, 4), True)
        self.assertEquals (field.checkWin (8, field.rows-2, 4), True)
        self.assertEquals (field.checkWin (7, field.rows-3, 4), True)
        self.assertEquals (field.checkWin (6, field.rows-4, 4), True)
        self.assertEquals (field.checkWin (7, field.rows-1, 4), False) 
        

if __name__ == '__main__':
    unittest.main()

