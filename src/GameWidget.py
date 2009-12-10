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
        self.aiActive = False
        
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
        self.layoutCreated = False
        
        self.winnerBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "0", "0", QtGui.QMessageBox.Ok, self)
        self.errorBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "0", "0", QtGui.QMessageBox.Ok, self)
        
        #ensure threading safety:
        self.lock = threading.Condition()
        
        if(type == self.CREATE_NEW_GAME):
            self.manyInARow = ManyInARowGame.hostGame(service, player, self.gameName, self.comment, self.nrRows, self.nrCols, self.waitTime,
                                                    self.chatCallBack,
                                                    self.gameJoinedCallBack,
                                                    self.playerJoinedCallBack, self.playerLeftCallBack,
                                                    self.moveCallBack, self.enableClicks, self.disableClicks,
                                                    self.playerWonCallBack, self.gameFinishedCallBack,
                                                    self.freezeCallback, self.unfreezeCallback)
            if(not self.layoutCreated):
                self.createLayout()
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
            
            self.manyInARow.start()
            
        if(type == self.JOIN_GAME):
            self.gameUUID = info['UUID']
            self.manyInARow = ManyInARowGame.joinGame(service, player, self.gameUUID, self.gameName, self.comment, self.nrRows, self.nrCols, self.waitTime,
                                                    self.chatCallBack,
                                                    self.gameJoinedCallBack,
                                                    self.playerJoinedCallBack, self.playerLeftCallBack,
                                                    self.moveCallBack, self.enableClicks, self.disableClicks,
                                                    self.playerWonCallBack, self.gameFinishedCallBack,
                                                    self.freezeCallback, self.unfreezeCallback)
            
            self.gameUUID = self.manyInARow.UUID
            self.startTime = self.manyInARow.startTime
            
            self.manyInARow.start()
        
        
    def getGameUUID(self):
        return self.gameUUID
    
    def aiToggled(self, state):
        if(state == QtCore.Qt.Checked):
            print "ai active"
            self.aiActive = True
            if(not self.scene.rejectClicks):
                self.scene.block(False)
                self.manyInARow._makeAiMove(self.players)
        else:
            print "ai inactive"
            self.aiActive = False
    
    
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
            if(self.aiActive):
                self.errorBox.setWindowTitle("AI is playing")
                self.errorBox.setText("The A.I. is currently playing, uncheck the checkbox to enable normal game mode.")
            else:
                self.scene.block(False)
                self.manyInARow.makeMove(column)
        
    def freezeGame(self):
        print "Freezing the game"
        with self.lock:
            self.freezeButton.setDisabled(True)
            self.freezeButton.setText("Unfreeze")
            self.freezeButton.clicked.disconnect(self.freezeGame)
            self.freezeButton.clicked.connect(self.unfreezeGame)
            
            self.manyInARow.freezeGame()
        
    def unfreezeGame(self):
        print "Unfreezing the game"
        with self.lock:
            self.freezeButton.setDisabled(True)
            self.freezeButton.setText("Freeze")
            self.freezeButton.clicked.disconnect(self.unfreezeGame)
            self.freezeButton.clicked.connect(self.freezeGame)
            
            self.manyInARow.unfreezeGame()
    
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
            
            if(not self.layoutCreated):
                self.createLayout()
            
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("playerClicked(int)"), self.makeMove)
            QtCore.QObject.connect(self.scene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.makeHoverMove)
        
    
    def enableClicks(self):
        print "enableClicks"
        with self.lock:                
            self.freezeButton.setEnabled(True)
            if(self.scene != None):
                self.scene.unblock(False)
            
            if(self.aiActive):
                self.manyInARow._makeAiMove(self.players)
                
    def disableClicks(self):
        print "disable clicks"
        with self.lock:
            self.freezeButton.setDisabled(True)
            if(self.scene != None):
                self.scene.block(False)
    
    
    def playerJoinedCallBack(self, playerUUID, newPlayer):
        print "playerJoinedCallBack"
        with self.lock:
            if(not self.layoutCreated):
                self.createLayout()
        
            if playerUUID not in self.players.keys():
                self.logList.addMessage(newPlayer, "successfully joined")
            self.players[playerUUID] = newPlayer
            self.ui.playerList.clear();
            for currentPlayer in self.players.values():
                currentPlayer
                newItem = QtGui.QListWidgetItem(currentPlayer.name, self.ui.playerList)
                newItem.setBackgroundColor(QtGui.QColor(currentPlayer.color[0], currentPlayer.color[1], currentPlayer.color[2]))
                self.ui.playerList.addItem(newItem)
            
            
    def playerLeftCallBack(self, playerUUID):
        print "playerLeftCallBack"
        with self.lock:
            self.logList.addMessage(self.players[playerUUID], "has left")
                
            del self.players[playerUUID]
            self.ui.playerList.clear();
            for currentPlayer in self.players.values():
                newItem = QtGui.QListWidgetItem(currentPlayer.name, self.ui.playerList)
                newItem.setBackgroundColor(QtGui.QColor(currentPlayer.color[0], currentPlayer.color[1], currentPlayer.color[2]))
                self.ui.playerList.addItem(newItem)


    def chatCallBack(self, playerUUID, message):
        print "chatCallBack"
        with self.lock:
            self.logList.addMessage(self.players[playerUUID], "said: " + message)
            color = QtGui.QColor(self.players[playerUUID].color[0], self.players[playerUUID].color[1], self.players[playerUUID].color[2])
            playerName = self.players[playerUUID].name
            newItem = QtGui.QListWidgetItem(playerName + ": " + message, self.ui.messageList)
            newItem.setBackgroundColor(color)
            self.ui.messageList.addItem(newItem)
        
    
    def moveCallBack(self, playerUUID, col, row):
        print "moveCallBack"
        with self.lock:
            self.logList.addMessage(self.players[playerUUID], "placed: (column, row) - (" + str(col) + ", " + str(row) + ")")
            self.scene.makeMove(col, row, QtGui.QColor(self.players[playerUUID].color[0], self.players[playerUUID].color[1], self.players[playerUUID].color[2]))
    
    def playerWonCallBack(self, winners, currentGoal):
        print "playerWonCallBack"
        with self.lock:
            winnerUUID = winners[currentGoal]
            self.logList.addMessage(self.players[winnerUUID], "has won round " + str(currentGoal))
            name = self.players[winnerUUID].name
            self.winnerBox.setWindowTitle("Round finished in game:  " + "\'"+self.gameName+"\'")
            self.winnerBox.setText(name + " has won this round")
            self.winnerBox.show()
        
    def gameFinishedCallBack(self, winners):
        self.logList.addMessage(self.player, "the game has finished")
        print "gameFinishedCallBack"
        winnerStr = ""
        with self.lock:
            for winner in winners.items():
                winnerStr = winnerStr + str(winner[0]) + " in a row: " + self.players[winner[1]].name + "\n"
                
            self.winnerBox.setWindowTitle("Game " + "\'"+self.gameName+"\'" + "finished")
            self.winnerBox.setText("The game has finished, the winners are: \n" + winnerStr)
            self.winnerBox.show()
            
    def freezeCallback(self):
        print "freezing via callback"
        with self.lock:
            self.freezeButton.setText("Unfreeze")
            self.freezeButton.clicked.disconnect(self.freezeGame)
            self.freezeButton.clicked.connect(self.unfreezeGame)
            self.freezeButton.setEnabled(True)
            self.scene.block(True)
            
    def unfreezeCallback(self):
        print "unfreezing via callback"
        with self.lock:
            self.freezeButton.setEnabled(True)
            self.freezeButton.setText("Freeze")
            self.freezeButton.clicked.disconnect(self.unfreezeGame)
            self.freezeButton.clicked.connect(self.freezeGame)
            self.scene.unblock(True)
    
    def makeHoverMove(self, column):
        print "hover column: " + str(column)
        with self.lock:
            if(not self.aiActive):
                row = self.manyInARow._makeDummyMove(column)
                if(row != -1):
                    #update the gui
                    color = QtGui.QColor(self.player.color[0], self.player.color[1], self.player.color[2])
                    self.scene.makeDummyMove(column, row, color)
                
        
    
    def createLayout(self):
        self.ui = uic.loadUi("GameWidget.ui", self)
        self.scene = GraphicsScene(self.nrRows, self.nrCols, QtGui.QColor(self.player.color[0], self.player.color[1], self.player.color[2]), self)
        self.scene.block(False)
        self.ui.graphicsView.setScene(self.scene)
        self.logList = LogWidget(self)
        self.logList.setMaximumSize(250, 200)
        self.freezeButton = QtGui.QPushButton("Freeze", self)
        self.freezeButton.clicked.connect(self.freezeGame)
        self.freezeButton.setDisabled(True)
        self.ui.verticalLayout.addWidget(self.logList)
        self.ui.verticalLayout.addWidget(self.freezeButton)
        self.ui.chatEdit.returnPressed.connect(self.sendMessage)
        self.ui.aiCheckBox.stateChanged.connect(self.aiToggled)
        self.ui.show()
        self.layoutCreated = True
        
    def closeEvent(self, event):
        if(self.manyInARow != None):
            self.manyInARow.kill()