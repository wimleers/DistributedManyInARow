from PyQt4 import QtGui, QtCore
import sys
from GameWidget import GameWidget
from PlayerAddWidget import PlayerAddWidget
from NetworkLobbyWidget import NetworkLobbyWidget
from ManyInARowService import ManyInARowService
from DistributedGame.Player import Player
import threading

class MainWindow(QtGui.QMainWindow):
    def __init__(self, win_parent = None):
        QtGui.QMainWindow.__init__(self, win_parent)
        
        self.games = []
        
        #ensure threading safety:
        self.lock = threading.Condition()
        
        #GUI
        self.createLayout()
        self.createMenu()
        self.show()
        self.succesBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "Success", "Service started successfully", QtGui.QMessageBox.Ok, self)
        self.errorBox = QtGui.QMessageBox(QtGui.QMessageBox.Critical, "Error", "Service registration failed, please restart.", QtGui.QMessageBox.Ok, self)
        
        playerAddWidget = PlayerAddWidget(self)
        localPlayerName = playerAddWidget.getPlayerInfo()
        self.localPlayer = Player(str(localPlayerName))
        
        #Network
        self.manyInARowService = ManyInARowService(self.localPlayer, self.serviceRegisteredCallback, self.serviceRegistrationFailedCallback,
                                                   self.serviceUnregisteredCallback, self.peerServiceDiscoveredCallback,
                                                   self.peerServiceRemovedCallback, self.playerAddedCallback, self.playerUpdatedCallback,
                                                   self.playerLeftCallback, self.gameAddedCallback,
                                                   self.gameUpdatedCallback, self.gameEmptyCallback)
        
        self.manyInARowService.start()
        
    def closeEvent(self, event):
        with self.lock:
            self.manyInARowService.kill()
            for i in range(len(self.games)):
                self.games[i].close()
                
            event.accept()
        
    def createLayout(self):
        #Left side of screen: List of availabe games
        #Right side of screen: TabWidget showing all the games in which the player is participating
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.mainWidget = QtGui.QWidget(self)
        self.mainWidget.setLayout(self.horizontalLayout)
        
        self.networkLobby = NetworkLobbyWidget(self)
        QtCore.QObject.connect(self.networkLobby, QtCore.SIGNAL("joinGameClicked(PyQt_PyObject, QString)"), self.joinGame)
        QtCore.QObject.connect(self.networkLobby, QtCore.SIGNAL("addGame()"), self.createNewGame)
        self.leftLayout = QtGui.QVBoxLayout()
        self.leftLayout.addWidget(self.networkLobby)
        
        self.tabWidget = QtGui.QTabWidget(self)
        
        self.horizontalLayout.addLayout(self.leftLayout, 2)
        self.horizontalLayout.addWidget(self.tabWidget, 15)
        self.setCentralWidget(self.mainWidget)
        
    def createMenu(self):
        gameMenu = QtGui.QMenu("&Game", self)
        newGameAct = QtGui.QAction("Start &new", gameMenu)
        newGameAct.triggered.connect(self.createNewGame)
        quitAct = QtGui.QAction("&Close", gameMenu)
        quitAct.triggered.connect(self.close)
        gameMenu.addAction(newGameAct)
        gameMenu.addAction(quitAct)
        self.menuBar().addMenu(gameMenu)
        
    def createNewGame(self):
        newGameDialog = NewGameDialog(self)
        (gameName, gameComment, numRows, numCols, waitTime) = newGameDialog.getGameInfo()
        if(gameName != None):
            self.games.append(GameWidget(GameWidget.CREATE_NEW_GAME, {'rows' : numRows, 'cols' : numCols, 'name' : gameName, 'comment' : gameComment, 'waitTime' : waitTime}, self.localPlayer, self.manyInARowService, self.tabWidget))
            self.tabWidget.addTab(self.games[len(self.games) - 1], gameName)
    
    def joinGame(self, UUID, name):
        # Is called when the user chooses to join a network game. This functions makes sure a new tab is created and the game joining is intiated. 
        # Create the new tab
        with self.lock:
            info = self.networkLobby.getGameInfo(UUID)
            self.games.append(GameWidget(GameWidget.JOIN_GAME, info , self.localPlayer, self.manyInARowService, self.tabWidget))
            self.tabWidget.addTab(self.games[len(self.games) - 1], name)
        
    def serviceRegisteredCallback(self, name, regtype, port):
        print "serviceRegisteredCallback"
        """with self.lock:
            self.succesBox.exec_()
        """
    def serviceRegistrationFailedCallback(self, name, errorCode, errorMessage):
        print "serviceRegistrationFailedCallback"
        with self.lock:
            self.errorBox.setText(str(errorCode) + ": " + str(errorMessage))
            self.errorBox.exec_()
            self.close()
    
    def serviceUnregisteredCallback(self, serviceName, serviceType, port):
        print "serviceUnregisteredCallback" 
        pass
    
    def peerServiceDiscoveredCallback(self, serviceName, interfaceIndex, ip, port):
        print "peerServiceDiscoveredCallback" 
        with self.lock:
            self.networkLobby.addPeer(serviceName, interfaceIndex, ip, port)
    
    def peerServiceRemovedCallback(self, serviceName, interfaceIndex):
        print "peerServiceRemovedCallback" 
        with self.lock:
            self.networkLobby.removePeer(serviceName, interfaceIndex)
        
    def playerAddedCallback(self, player):
        print "playerAddedCallback" 
        with self.lock:
            self.networkLobby.addPlayer(player)
    
    def playerUpdatedCallback(self, player):
        print "playerUpdatedCallback"
        with self.lock:
            self.networkLobby.updatePlayer(player)
    
    def playerLeftCallback(self, player):
        print "playerLeftCallback" 
        with self.lock:
            print "Player left: " + str(player)
            self.networkLobby.removePlayer(player)
    
    def gameAddedCallback(self, gameUUID, newGame):
        with self.lock:
            self.networkLobby.addGame(newGame, gameUUID)
    
    def gameUpdatedCallback(self, updatedGame):
        pass
    
    def gameEmptyCallback(self, emptyGameUUID, UUID):
        print "gameEmptyCallback" 
        #remove the game tab for this game
        with self.lock:
            self.networkLobby.removeGame(emptyGameUUID)
    

class NewGameDialog(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        self.createLayout()
        
        self.gameName = ""
        self.gameComment = ""
        
    def getGameInfo(self):
        #can be called when we want to launch a new game. Returns the values needed to create a new game
        self.exec_()
        if(self.result() == 1):
            #if the dialog was accepted (start game was clicked)
            return (self.gameName, self.gameComment, self.numRows, self.numCols, self.waitTime)
        else:
            return (None, None, None, None, None)
        
    def createLayout(self):
        gridLayout = QtGui.QGridLayout(self)
        label = QtGui.QLabel("New game parameters: ", self)
        label2 = QtGui.QLabel("Name: ", self)
        label3 = QtGui.QLabel("Comment: ", self)
        label4 = QtGui.QLabel("# Rows: ", self)
        label5 = QtGui.QLabel("# Cols: ", self)
        label6 = QtGui.QLabel("Time between moves (secs)", self)
        self.gameEdit = QtGui.QLineEdit("testgame",self)
        self.commentEdit = QtGui.QLineEdit("testcomment", self)
        self.numRowEdit = QtGui.QSpinBox(self)
        self.numRowEdit.setMinimum(1)
        self.numRowEdit.setMaximum(30)
        self.numRowEdit.setValue(5)
        self.numColEdit = QtGui.QSpinBox(self)
        self.numColEdit.setMinimum(1)
        self.numColEdit.setMaximum(30)
        self.numColEdit.setValue(5)
        self.waitTimeEdit = QtGui.QSpinBox(self)
        self.waitTimeEdit.setMinimum(1)
        self.waitTimeEdit.setMaximum(100)
        self.waitTimeEdit.setValue(1)
        startButton = QtGui.QPushButton("&Start", self)
        startButton.clicked.connect(self.paramsSet)
        cancelButton = QtGui.QPushButton("&Cancel", self)
        cancelButton.clicked.connect(self.reject)
        
        gridLayout.addWidget(label, 0, 0, 1, 2)
        gridLayout.addWidget(label2, 1, 0)
        gridLayout.addWidget(label3, 2, 0)
        gridLayout.addWidget(label4, 3, 0)
        gridLayout.addWidget(label5, 4, 0)
        gridLayout.addWidget(label6, 5, 0)
        gridLayout.addWidget(self.gameEdit, 1, 1)
        gridLayout.addWidget(self.commentEdit, 2, 1)
        gridLayout.addWidget(self.numRowEdit, 3, 1)
        gridLayout.addWidget(self.numColEdit, 4, 1)
        gridLayout.addWidget(self.waitTimeEdit, 5, 1)
        gridLayout.addWidget(startButton, 6, 0)
        gridLayout.addWidget(cancelButton, 6, 1)
        
    def paramsSet(self):
        self.gameName = self.gameEdit.text()
        self.gameComment = self.gameEdit.text()
        self.numRows = self.numRowEdit.value()
        self.numCols = self.numColEdit.value()
        self.waitTime = self.waitTimeEdit.value()
        if(self.gameName == "" or self.gameComment == ""):
            QtGui.QMessageBox.warning(self, "Incomplete", "Not all values were set correctly.")
        else:
            self.accept()
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    app.exec_()