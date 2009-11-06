from PyQt4 import QtGui, QtCore
import sys
from GameWidget import GameWidget
from PlayerAddWidget import PlayerAddWidget
import vieropeenrij

class MainWindow(QtGui.QMainWindow):
    def __init__(self, win_parent = None):
        QtGui.QMainWindow.__init__(self, win_parent)
        
        self.createLayout()
        self.createMenu()
        self.showMaximized()
        startDialog = StartDialog(self)
        QtCore.QObject.connect(startDialog, QtCore.SIGNAL("startNewGame()"), self.createNewGame)
        startDialog.exec_()
        
    def createLayout(self):
        self.gridLayout = QtGui.QGridLayout()
        self.tabWidget = QtGui.QTabWidget(self)
        self.setCentralWidget(self.tabWidget)        
        
    def createMenu(self):
        gameMenu = QtGui.QMenu("&Game", self)
        newGameAct = QtGui.QAction("Start &new", gameMenu)
        newGameAct.triggered.connect(self.createNewGame)
        joinGameAct = QtGui.QAction("&Join existing", gameMenu)
        joinGameAct.triggered.connect(self.joinGame)
        gameMenu.addAction(newGameAct)
        gameMenu.addAction(joinGameAct)
        self.menuBar().addMenu(gameMenu)
        
    def createNewGame(self):
        #TODO: implement. Start a new game using interface for network functionality
        newGameDialog = NewGameDialog(self)
        (gameName, gameComment, inARow, numRows, numCols) = newGameDialog.getGameInfo()
        if(gameName != None):
            self.tabWidget.addTab(GameWidget(numRows, numCols, inARow, self.tabWidget), gameName)
        
    def joinGame(self):
        #TODO: implement. Launch dialog asking which game to join
        x = 1
        
class StartDialog(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        
        self.createLayout()
        
    def createLayout(self):
        self.layout = QtGui.QHBoxLayout(self)
        startNewGameButton = QtGui.QPushButton("Start a game", self)
        startNewGameButton.clicked.connect(self.startNewGameClicked)
        joinGameButton = QtGui.QPushButton("Join a game", self)
        joinGameButton.clicked.connect(self.joinGameClicked)
        self.layout.addWidget(startNewGameButton)
        self.layout.addWidget(joinGameButton)
        
    def startNewGameClicked(self):
        self.emit(QtCore.SIGNAL("startNewGame()"))
        self.accept()
        
    def joinGameClicked(self):
        self.emit(QtCore.SIGNAL("joinGame()"))
        self.accept()
        
        #TODO: buttons moeten signal nog doorgeven aan mainwindow zodat correct venster geopend kan worden
        
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
            return (self.gameName, self.gameComment, self.inARow, self.numRows, self.numCols)
        else:
            return (None, None, None, None, None)
        
    def createLayout(self):
        gridLayout = QtGui.QGridLayout(self)
        label = QtGui.QLabel("New game parameters: ", self)
        label2 = QtGui.QLabel("Name: ", self)
        label3 = QtGui.QLabel("Comment: ", self)
        label4 = QtGui.QLabel("# Rows: ", self)
        label5 = QtGui.QLabel("# Cols: ", self)
        label6 = QtGui.QLabel("# In a row: ", self)
        self.gameEdit = QtGui.QLineEdit(self)
        self.commentEdit = QtGui.QLineEdit(self)
        self.numRowEdit = QtGui.QSpinBox(self)
        self.numRowEdit.setMinimum(1)
        self.numRowEdit.setMaximum(30)
        self.numRowEdit.setValue(1)
        self.numColEdit = QtGui.QSpinBox(self)
        self.numColEdit.setMinimum(1)
        self.numColEdit.setMaximum(30)
        self.numColEdit.setValue(1)
        self.inARowEdit = QtGui.QSpinBox(self)
        self.inARowEdit.setMinimum(2)
        self.inARowEdit.setMaximum(30)
        self.inARowEdit.setValue(2)
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
        gridLayout.addWidget(self.inARowEdit, 5, 1)
        gridLayout.addWidget(startButton, 6, 0)
        gridLayout.addWidget(cancelButton, 6, 1)
        
    def paramsSet(self):
        self.gameName = self.gameEdit.text()
        self.gameComment = self.gameEdit.text()
        self.inARow = self.inARowEdit.value()
        self.numRows = self.numRowEdit.value()
        self.numCols = self.numColEdit.value()
        if(self.gameName == "" or self.gameComment == ""):
            QtGui.QMessageBox.warning(self, "Incomplete", "Not all values were set correctly.")
        else:
            self.accept()
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    app.exec_()
    
    
"""Following code was used as an example and can be used for future reference:
def __init__(self, win_parent = None):
        QtGui.QMainWindow.__init__(self, win_parent)
        
        #testing:
        self.newGame(10, 15)
        self.localGameTest()
        
        self.createMenu()

    def newGame(self, nrRows = 7, nrCols = 7):
        self.createLayout(nrRows, nrCols)
        
    def localGameTest(self):
        self.inARow = 4
        self.players = vieropeenrij.Players()
        self.field = vieropeenrij.Field(10, 15)
        self.players.addPlayer(vieropeenrij.Player("Brecht", QtGui.QColor(0, 20, 250)))
        self.players.addPlayer(vieropeenrij.Player("Kristof", QtGui.QColor(255, 20, 0)))
        QtCore.QObject.connect(self.graphicsScene, QtCore.SIGNAL("playerClicked(int)"), self.localGameClickTest)
        QtCore.QObject.connect(self.graphicsScene, QtCore.SIGNAL("mouseHoverColumn(int)"), self.localGameHoverTest)
        
    def localGameClickTest(self, move):
        print "Move" + str(move)
        valid = self.field.makeMove (move, self.players.currentPlayer)
        if(valid != -1):
            #update GUI:
            color = self.players.getCurrentPlayerColor()
            self.graphicsScene.makeMove(move, valid, color)
        else:
            return
        
        won = self.field.checkWin(move, valid, self.inARow)
        if won:
            QtGui.QMessageBox.information(self, "Spel afgelopen", "Speler " + self.players.getCurrentPlayerName() + " heeft gewonnen!")
        else:
            self.players.getNextPlayer()
            
    def localGameHoverTest(self, columnIndex):
        valid = self.field.getRowIndexByColumn(columnIndex)
        print 'Valid: ' + str(valid)
        if(valid != -1):
            #update the gui
            color = self.players.getCurrentPlayerColor()
            self.graphicsScene.makeDummyMove(columnIndex, valid, color)
            
"""