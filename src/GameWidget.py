from PyQt4 import QtGui, QtCore
from PyQt4 import uic
from GraphicsScene import GraphicsScene
from LogWidget import LogWidget
from ManyInARowGame import ManyInARowGame
from DistributedGame.Player import Player
import vieropeenrij

class GameWidget(QtGui.QWidget):
#GameWidget provides a window in which a game can be played. It displays the gameboard(GraphicsScene),
#active players, log messages and chat messages

    CREATE_NEW_GAME, JOIN_GAME = range(2)
    def __init__(self, type, info, player, service, win_parent = None):
        # If type is CREATE_NEW_GAME, info contains the number of rows and colums, name and comment.
        # If type is JOIN_GAME, info contains the UUID of the game the user wishes to join.
        QtGui.QWidget.__init__(self, win_parent)
        
        self.scene = None
        
        self.manyInARowService = service
        self.player = player
        
        self.nrCols = None
        self.nrRows = None
        self.gameName = None
        self.comment = None
        self.waitTime = None
        self.startTime = None
        self.players = []
        
        # Create a ManyInARowGame instance and try to join the game
        self.manyInARow = ManyInARowGame(self.manyInARowService, self.player,
                                        self.chatCallBack,
                                        self.gameJoinedCallBack,
                                        self.addPlayerCallBack, self.updatePlayerCallBack, self.removePlayerCallBack,
                                        self.moveCallBack, self.enableClicks,
                                        self.playerWonCallBack, self.gameFinishedCallBack)
        
        if(type == self.CREATE_NEW_GAME):
            """ The following data is retrieved when starting a new game. The service automatically launches a callback
                to pass the correct settings of the game.
            self.nrRows = info['rows']
            self.nrCols = info['cols']
            self.gameName = info['name']
            self.comment = info['comment']
            self.waitTime = info['waitTime']
            """
            self.manyInARow.host(info['name'], info['comment'], info['rows'], info['cols'], info['waitTime'])
            
            
        if(type == self.JOIN_GAME):
            self.gameUUID = info
            self.manyInARow.join(info)
        
        
    def getGameUUID(self):
        return self.gameUUID
    
    
    # Functions the user can trigger:
    def sendMessage(self):
        message = self.ui.chatEdit.text()
        self.ui.chatEdit.clear()
        
        self.manyInARow.sendChatMessage(message)
    
    
    def makeMove(self, column):
        # Passes the move to the class coordinating the game (ManyInARowGame)
        print "Dropped in column: " + str(column)
        self.scene.block()
        self.manyInARow.makeMove(column)
    
    # Callbacks:
    def gameJoinedCallBack(self, name, description, numRows, numCols, waitTime, startTime):
        print "gameJoinedCallBack"
        # We know the number of rows and colums, build the GUI board.
        self.nrCols = numCols
        self.nrRows = numRows
        self.gameName = name
        self.comment = description
        self.waitTime = waitTime
        self.startTime = startTime
        
        self.createLayout()
        
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
    
    
    def enableClicks(self):
        print "enableClicks"
        if(self.scene != None):
            self.scene.unblock()
    
    
    def addPlayerCallBack(self, playerUUID, newPlayer):
        print "addPlayerCallBack"
        #playerUUID = new player's UUID
        #newplayer = new players object
        newItem = QtGui.QListWidgetItem(playerName, self.ui.playerList)
        newItem.setBackgroundColor(QtGui.QColor(newPlayer.color[0], newPlayer.color[1], newPlayer.color[2]))
        self.ui.playerList.addItem(newItem)
        
        self.players[playerUUID] = newPlayer
        
        
    def updatePlayerCallBack(self, playerUUID, updatedPlayer):
        print "updatePlayerCallBack"
        self.players[playerUUID] = updatedPlayer
    
    
    def removePlayerCallBack(self, playerUUID):
        print "removePlayerCallBack"
        items = self.ui.playerList.findItems(playerName)
        for item in items:
            self.ui.playerList.removeItemWidget(item)
            
        del self.players[playerUUID]


    def chatCallBack(self, playerUUID, message):
        print "chatCallBack"
        color = QtGui.QColor(self.players[playerUUID].color[0], self.players[playerUUID].color[1], self.players[playerUUID].color[2])
        newItem = QtGui.QListWidgetItem(playerName + ": " + message, self.ui.messageList)
        newItem.setBackgroundColor(color)
        self.ui.messageList.addItem(newItem)
        
    
    def moveCallBack(self, playerUUID, move):
        print "moveCallBack"
        #todo: implement
        pass
    
    def playerWonCallBack(self, winners, index):
        print "playerWonCallBack"
        winnerUUID = winners[index]
        name = self.players[winnerUUID]
        QtGui.QMessageBox.information(self, "Round finished. ", name + " has won this round")
        
    def gameFinishedCallBack(self, winners):
        print "gameFinishedCallBack"
        i = 0
        winnerStr = ""
        for winnerUUID in winners:
            winnerStr = winnerStr + str(i) + " in a row: " + self.players[winnerUUID] + "\n"
            
        QtGui.QMessageBox.information(self, "Game finished", "The game has finished, the winners are: " + winnerStr)
    
    def makeHoverMove(self, column):
        valid = self.field.getRowIndexByColumn(column)
        if(valid != -1):
            #update the gui
            color = self.players.getCurrentPlayerColor()
            self.scene.makeDummyMove(column, valid, color)
        
    
    def createLayout(self):
        self.ui = uic.loadUi("GameWidget.ui", self)
        self.scene = GraphicsScene(self.nrRows, self.nrCols, self)
        self.ui.graphicsView.setScene(self.scene)
        self.logList = LogWidget(self)
        self.logList.setMaximumSize(250, 200)
        self.ui.verticalLayout.addWidget(self.logList)
        self.ui.chatEdit.returnPressed.connect(self.sendMessage)
        self.ui.show()