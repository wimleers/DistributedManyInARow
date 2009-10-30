

class Player:
    def __init__ (self, name, colour):
        self.name = name
        self.colour = colour
        self.status = 'active'
    def __str__ (self):
        return 'Player ' + self.name + ' with colour ' + self.colour + ' and status: ' + self.status

class Players:
    def __init__ (self):
        self.numPlayers = 0
        self.players = []
        self.currentPlayer = 0

    def addPlayer (self, player):
        self.players.append (player)
        self.numPlayers = self.numPlayers + 1

    def deletePlayer (self, player):
        for p in self.players:
            if player.colour == p.colour:
                p.status = 'left'
        
        #if the player who left is the current player, we give the turn to the previous player again
        if self.players[self.currentPlayer].colour == player.colour:
            self.currentPlayer = self.currentPlayer -1
            if (self.currentPlayer < 0):
                self.currentPlayer = self.numPlayers - 1     

    def getCurrentPlayerName (self):
        return self.players[self.currentPlayer].name
    
    def getCurrentPlayerColor(self):
        return self.players[self.currentPlayer].colour
        
    def getNextPlayer (self):
        self.currentPlayer = self.currentPlayer + 1
        self.currentPlayer = self.currentPlayer % self.numPlayers
        if self.players[self.currentPlayer].status != 'active':
            self.getNextPlayer()

    def printPlayers (self):
        for player in self.players:
            print player

class Field:
    def __init__ (self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.values = [[-1 for i in xrange(cols)] for j in xrange(rows)]

    def makeMove (self, x, player):
        
        for i in range (self.rows, -1, -1):
            if self.checkMove (x, i):
                self.values[i][x] = player
                return i
        return -1
    
    def getRowIndexByColumn(self, x):
        #returns the next block index of the row in the given column ( used to show the user where the next block will fall )
        for i in range (self.cols, -1, -1):
            if self.checkMove (x, i):
                return i
        return -1


    def checkMove (self, x, y):
        if self.rows > y and self.cols > x:
            return self.values[y][x] == -1
        else:
            return False

    def checkWin (self, x, y, inARow):
        if (self.values[y][x] != -1):
            found = True
            won = False
            
            startX = x
            startY = y        
            for i in range (1, inARow):
                if (self.values[y][x-i] == self.values[y][x]) and x-i >= 0:
                    startX = x - i
            
            if startX + inARow - 1 < self.cols:
                for i in range (startX+1, startX + inARow):
                    if (self.values[y][i] != self.values[y][startX]):
                        found = False
            else:
                found = False
            if found:
                won = True

            startX = x
            startY = y        
            for i in range (1, inARow):
                if (y - i >= 0 and self.values[y-i][x] == self.values[y][x]):
                    startY = y - i

            found = True
            if startY + inARow - 1 < self.rows:
                for i in range (startY+1, startY + inARow):
                    if (self.values[i][x] != self.values[startY][x]):
                        found = False

            else:
                found = False
            if found:
                won = True

            startX = x
            startY = y   
         
            for i in range (1, inARow):
                if (y + i < self.rows and x-i >= 0 and self.values[y+i][x-i] == self.values[x][y]):
                    startY = y + i
                    startX = x- i
            found = True
            if startY - inARow + 1 > 0 and startX + inARow - 1 < self.cols:
                for i in range (1,inARow):
                    if (self.values[startY - i][startX+i] != self.values[startY][startX]):
                        found = False

            else:
                found = False
            if found:
                won = True

            startX = x
            startY = y   
         
            for i in range (1, inARow):
                if (y + i < self.rows and x + i < self.cols and self.values[y+i][x+i] == self.values[y][x]):
                    startY = y + i
                    startX = x + i

            found = True
            if startY - inARow + 1 >= 0 and startX - inARow + 1 >= 0:
                for i in range (1,inARow):
                    if (self.values[startY-i][startX-i] != self.values[startY][startX]):
                        found = False

            else:
                found = False
            if found:
                won = True

            return won
        else:
            return False

    def __str__(self):
        
        string = '   '
        for x in range (0, self.cols):  
            string = string + ' ' + str(x) + ' '
        string = string + '\n'
        for y in range (0, self.rows):
            string = string + ' ' + str(y) + ' '
            for x in range (0, self.cols):  
                if self.values[y][x] == -1:
                    string = string + ' x '
                else:
                    string = string + ' ' + str(self.values[y][x]) + ' '
            string = string + '\n'
        return string

class game:
    def __init__ (self):
        self.inARow = 4
        self.players = Players()
        self.field = Field(10, 15)
        self.players.addPlayer (Player(raw_input('Name for player 1: '), 'blue'))
        self.players.addPlayer (Player(raw_input('Name for player 2: '), 'red'))
    def play(self):
        won = False
        while not won:
            print self.field
            move = int(raw_input(self.players.getCurrentPlayerName() + '\'s turn! Give the x coordinate for the next move: '))
            valid = self.field.makeMove (move, self.players.currentPlayer)
    
            while valid == -1:
                move = int(raw_input(self.players.getCurrentPlayerName() + '\'s turn! Please give a correct move: '))
                valid = self.field.makeMove (move, self.players.currentPlayer)

            won = self.field.checkWin(move, valid, self.inARow)
            if won:
                print self.players.getCurrentPlayerName() + ' has won!'
                feedback = raw_input('Do you want to continue playing with 1 more needed row for a win? y/N')
                if feedback == 'y':
                    won = False
                    self.players.getNextPlayer()
                    self.inARow = self.inARow + 1
            else:
                self.players.getNextPlayer()
        
        

            


"""players = Players()
players.addPlayer (Player('Kristof', 'red'))
players.addPlayer (Player('Brecht', 'blue'))
players.addPlayer (Player('Wim', 'pink'))

#players.printPlayers()     
print players.getNextPlayer()
print players.getNextPlayer()
players.deletePlayer (Player('Brecht', 'blue'))
print players.getNextPlayer()
print players.getNextPlayer()


field = Field (10, 12)
field.makeMove (5, 1)
field.makeMove (1, 2)
field.makeMove (4, 3)
field.makeMove (4, 2)
field.makeMove (4, 3)
field.makeMove (3,2)
field.makeMove (5,2)
field.makeMove (5,2)
field.makeMove (6,3)
field.makeMove (6,2)
field.makeMove (6,2)
field.makeMove (6,2)
field.makeMove (4, 3)

field.makeMove (8,2)
field.makeMove (9,2)
field.makeMove (9,2)
field.makeMove (10,2)
field.makeMove (10,2)
field.makeMove (10,2)
field.makeMove (11,3)
field.makeMove (11,2)
field.makeMove (11,2)
field.makeMove (11,2)
print field
print field.checkWin (10, 5, 5)
"""

game().play()
