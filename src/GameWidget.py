from PyQt4 import QtGui, QtCore
from PyQt4 import uic
from GraphicsScene import GraphicsScene
from LogWidget import LogWidget
from ManyInARowGame import ManyInARowGame
import vieropeenrij

class GameWidget(QtGui.QWidget):
#GameWidget provides a window in which a game can be played. It displays the gameboard(GraphicsScene),
#active players, log messages and chat messages

    CREATE_NEW_GAME, JOIN_GAME = range(2)
    def __init__(self, type, info, playerName, win_parent = None):
        # If type is CREATE_NEW_GAME, info contains the number of rows and colums, name and comment.
        # If type is JOIN_GAME, info contains the UUID of the game the user wishes to join.
        QtGui.QWidget.__init__(self, win_parent)
        
        # Create a ManyInARowGame instance and try to join the game
        # Todo: add callback to set the number of rows and colums (self.gameInfoCallBack)
        #self.manyInARow = ManyInARowGame(playerName, self.moveCallBack, self.chatCallBack,
        #                             self.addPlayerCallBack, self.updatePlayerCallBack,
        #                             self.removePlayerCallBack, self.enableClicks)
        
        if(type == self.CREATE_NEW_GAME):
            self.nrRows = info['rows']
            self.nrCols = info['cols']
            self.gameName = info['name']
            comment = info['comment']
            waitTime = info['waitTime']
            #self.manyInARow.startGame(self.gameName, comment, self.nrRows, self.nrCols, waitTime)
            
            
        if(type == self.JOIN_GAME):
            self.gameUUID = info
            #self.manyInARow.joinGame(self.gameUUID)
            
        self.createLayout()
        
        
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
    def gameInfoCallBack(self, info):
        # We know the number of rows and colums, build the GUI board.
        self.createLayout()
        
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
        QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
    
    
    def enableClicks(self):
        self.scene.unblock()
    
    
    def addPlayerCallBack(self, playerUUID, newPlayer):
        #playername = string
        #color = QColor
        self.players.addPlayer(vieropeenrij.Player(playerName, color))
        newItem = QtGui.QListWidgetItem(playerName, self.ui.playerList)
        newItem.setBackgroundColor(color)
        self.ui.playerList.addItem(newItem)
        
        
    def updatePlayerCallBack(self, playerUUID, updatedPlayer):
        pass
    
    
    def removePlayerCallBack(self, playerUUID):
        #TODO: remove player from the list
        items = self.ui.playerList.findItems(playerName)
        for item in items:
            self.ui.playerList.removeItemWidget(item)


    def chatCallBack(self, playerUUID, message):
        #todo: implement
        color = self.players.getPlayerColor(playerName)
        if(color != -1):
            newItem = QtGui.QListWidgetItem(playerName + ": " + message, self.ui.messageList)
            newItem.setBackgroundColor(color)
            self.ui.messageList.addItem(newItem)
        
    
    def moveCallBack(self, playerUUID, move):
        #todo: implement
        pass
    
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