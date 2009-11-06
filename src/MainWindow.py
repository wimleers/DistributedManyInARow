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
        #TODO: implement. Launch dialog asking info needed to start new game
        x = 1
        self.tabWidget.addTab(GameWidget(5, 7, "1000", self.tabWidget), "bleeh")
        
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
        joinGameButton = QtGui.QPushButton("Join a game", self)
        
        self.layout.addWidget(startNewGameButton)
        self.layout.addWidget(joinGameButton)
        
        #TODO: buttons moeten signal nog doorgeven aan mainwindow zodat correct venster geopend kan worden
        
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