from PyQt4 import QtGui, QtCore
from PyQt4 import uic
from GraphicsScene import GraphicsScene
from LogWidget import LogWidget
import vieropeenrij

class GameWidget(QtGui.QWidget):
#GameWidget provides a window in which a game can be played. It displays the gameboard(GraphicsScene),
#active players, log messages and chat messages
    def __init__(self, nrRows, nrCols, inARow, gameUUID, win_parent = None):
        QtGui.QWidget.__init__(self, win_parent)
        
        self.nrRows = nrRows
        self.nrCols = nrCols
        self.inARow = inARow
        self.gameUUID = gameUUID
        self.createLayout()
        
        #initialize the backend:
        self.players = vieropeenrij.Players()
        self.field = vieropeenrij.Field(self.nrRows, self.nrCols)
        
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
        
        #test:
        self.addPlayer("Brecht", QtGui.QColor(255,0,0))
        self.addPlayer("Kristof", QtGui.QColor(0,255,0))
        self.addPlayer("Wim", QtGui.QColor(0,0,255))
        
    def getGameUUID(self):
        return self.gameUUID
    
    def addPlayer(self, playerName, color):
        #playername = string
        #color = QColor
        self.players.addPlayer(vieropeenrij.Player(playerName, color))
        newItem = QtGui.QListWidgetItem(playerName, self.ui.playerList)
        newItem.setBackgroundColor(color)
        self.ui.playerList.addItem(newItem)
    
    def removePlayer(self, playerName):
        #TODO: backend must be able to remove a player
        items = self.ui.playerList.findItems(playerName)
        for item in items:
            self.ui.playerList.removeItemWidget(item)
            
    def sendMessage(self):
        #todo: implement.
        x = 1
        
    def receiveMessage(self, playerName, message):
        #todo: implement
        x = 1
        
    def makeMove(self, column):
        #todo: implement (IMPORTANT: probably best practice to pass the move to the network class and only put it on the gameboard when we receive our own move in the buffer. This way a correct order is maintained)
        x = 1
        
    def makeHoverMove(self, column):
        valid = self.field.getRowIndexByColumn(column)
        if(valid != -1):
            #update the gui
            color = self.players.getCurrentPlayerColor()
            self.scene.makeDummyMove(column, valid, color)
        
    def receiveMove(self, player, move):
        #todo: implement
        x = 1
        
    def createLayout(self):
        self.ui = uic.loadUi("GameWidget.ui", self)
        self.scene = GraphicsScene(self.nrRows, self.nrCols, self)
        self.ui.graphicsView.setScene(self.scene)
        self.logList = LogWidget(self)
        self.logList.setMaximumSize(250, 200)
        self.ui.verticalLayout.addWidget(self.logList)
        self.ui.show()