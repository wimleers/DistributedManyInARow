from PyQt4 import QtGui, QtCore
from PyQt4 import uic
from GraphicsScene import GraphicsScene
from LogWidget import LogWidget
from ManyInARowGame import ManyInARowGame
from DistributedGame.Player import Player
import vieropeenrij
import threading

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
        
        self.nrCols = info['cols']
        self.nrRows = info['rows']
        self.gameName = str(info['name'])
        self.comment = str(info['comment'])
        self.waitTime = info['waitTime']
        self.startTime = None
        self.players = {}
        
        self.manyInARow = None
        
        #ensure threading safety:
        self.lock = threading.Condition()
        
        if(type == self.CREATE_NEW_GAME):
            self.manyInARow = ManyInARowGame.hostGame(service, player, self.gameName, self.comment, self.nrRows, self.nrCols, self.waitTime,
                                                    self.chatCallBack,
                                                    self.gameJoinedCallBack,
                                                    self.playerJoinedCallBack, self.playerLeftCallBack,
                                                    self.moveCallBack, self.enableClicks,
                                                    self.playerWonCallBack, self.gameFinishedCallBack)
            self.createLayout()
            self.manyInARow.start()
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
            
            
        if(type == self.JOIN_GAME):
            self.gameUUID = info['UUID']
            self.manyInARow = ManyInARowGame.joinGame(service, player, self.gameUUID, self.gameName, self.comment, self.nrRows, self.nrCols, self.waitTime,
                                                    self.chatCallBack,
                                                    self.gameJoinedCallBack,
                                                    self.playerJoinedCallBack, self.playerLeftCallBack,
                                                    self.moveCallBack, self.enableClicks,
                                                    self.playerWonCallBack, self.gameFinishedCallBack)
            
            self.gameUUID = self.manyInARow.UUID
            self.startTime = self.manyInARow.startTime
            self.manyInARow.start()           
        
        
    def getGameUUID(self):
        return self.gameUUID
    
    
    # Functions the user can trigger:
    def sendMessage(self):
        print self.ui.chatEdit.text()
        message = self.ui.chatEdit.text()
        self.ui.chatEdit.clear()
        
        self.manyInARow.sendChatMessage(message)
    
    
    def makeMove(self, column):
        # Passes the move to the class coordinating the game (ManyInARowGame)
        print "Dropped in column: " + str(column)
        with self.lock:
            self.scene.block()
        self.manyInARow.makeMove(column)
    
    # Callbacks:
    def gameJoinedCallBack(self, UUID, name, description, numRows, numCols, waitTime, startTime):
        print "gameJoinedCallBack"
        # We know the number of rows and colums, build the GUI board.
        with self.lock:
            self.gameUUID = UUID
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
            with self.lock:
                self.scene.unblock()
    
    
    def playerJoinedCallBack(self, playerUUID, newPlayer, newPlayerName):
        print "playerJoinedCallBack"
        #playerUUID = new player's UUID
        #newplayer = new players object
        with self.lock:
            newItem = QtGui.QListWidgetItem(newPlayerName, self.ui.playerList)
            newItem.setBackgroundColor(QtGui.QColor(newPlayer.color[0], newPlayer.color[1], newPlayer.color[2]))
            self.ui.playerList.addItem(newItem)
            
            self.players[playerUUID] = newPlayer
    
    def playerLeftCallBack(self, playerUUID):
        print "playerLeftCallBack"
        with self.lock:
            playername = self.players[playerUUID].name
            items = self.ui.playerList.findItems(playerName)
            for item in items:
                self.ui.playerList.removeItemWidget(item)
                
            del self.players[playerUUID]


    def chatCallBack(self, playerUUID, message):
        print "chatCallBack"
        with self.lock:
            color = QtGui.QColor(self.players[playerUUID].color[0], self.players[playerUUID].color[1], self.players[playerUUID].color[2])
            newItem = QtGui.QListWidgetItem(playerName + ": " + message, self.ui.messageList)
            newItem.setBackgroundColor(color)
            self.ui.messageList.addItem(newItem)
        
    
    def moveCallBack(self, playerUUID, col, row):
        print "moveCallBack"
        with self.lock:
            self.scene.makeMove(col, row, QtGui.QColor(self.players[playerUUID].color[0], self.players[playerUUID].color[1], self.players[playerUUID].color[2]))
    
    def playerWonCallBack(self, winners, currentGoal):
        print "playerWonCallBack"
        with self.lock:
            winnerUUID = winners[currentGoal]
            name = self.players[winnerUUID]
            QtGui.QMessageBox.information(self, "Round finished. ", name + " has won this round")
        
    def gameFinishedCallBack(self, winners):
        print "gameFinishedCallBack"
        i = 0
        winnerStr = ""
        with self.lock:
            for winnerUUID in winners:
                winnerStr = winnerStr + str(i) + " in a row: " + self.players[winnerUUID] + "\n"
                
            QtGui.QMessageBox.information(self, "Game finished", "The game has finished, the winners are: " + winnerStr)
    
    def makeHoverMove(self, column):
        with self.lock:
            row = self.manyInARow._makeDummyMove(column)
            if(row != -1):
                #update the gui
                color = QtGui.QColor(self.player.color[0], self.player.color[1], self.player.color[2])
                self.scene.makeDummyMove(column, row, color)
        
    
    def createLayout(self):
        self.ui = uic.loadUi("GameWidget.ui", self)
        self.scene = GraphicsScene(self.nrRows, self.nrCols, self)
        self.ui.graphicsView.setScene(self.scene)
        self.logList = LogWidget(self)
        self.logList.setMaximumSize(250, 200)
        self.ui.verticalLayout.addWidget(self.logList)
        self.ui.chatEdit.returnPressed.connect(self.sendMessage)
        self.ui.show()
        
    def closeEvent(self, event):
        print "Killing game"
        if(self.manyInARow != None):
            self.manyInARow.kill()