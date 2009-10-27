from PyQt4 import QtGui, QtCore
import sys

from GraphicsScene import GraphicsScene
from LogWidget import LogWidget
from PlayerAddWidget import PlayerAddWidget
import vieropeenrij

class MainWindow(QtGui.QMainWindow):
    def __init__(self, win_parent = None):
        QtGui.QMainWindow.__init__(self, win_parent)
        
        #testing:
        self.newGame(10, 10)
        self.localGameTest()

    def newGame(self, nrRows = 7, nrCols = 7):
        self.createLayout(nrRows, nrCols)
        
    def localGameTest(self):
        self.inARow = 4
        self.players = vieropeenrij.Players()
        self.field = vieropeenrij.Field(10, 10)
        self.players.addPlayer(vieropeenrij.Player("Brecht", QtGui.QColor(0, 20, 250)))
        self.players.addPlayer(vieropeenrij.Player("Kristof", QtGui.QColor(255, 20, 0)))
        QtCore.QObject.connect(self.graphicsScene, QtCore.SIGNAL("playerClicked(int)"), self.localGameClickTest)
        
    def localGameClickTest(self, move):
        valid = self.field.makeMove (move, self.players.currentPlayer)
        if(valid):
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
        
    def createLayout(self, nrRows, nrCols):
        self.gridLayout = QtGui.QGridLayout()
        self.widget = QtGui.QWidget(self)
        self.widget.setLayout(self.gridLayout)
        self.setCentralWidget(self.widget)
        
        self.graphicsScene = GraphicsScene(nrRows, nrCols, self)
        view = QtGui.QGraphicsView(self)
        view.setScene(self.graphicsScene)
        self.logWidget = LogWidget(self)
        
        self.gridLayout.addWidget(view, 0, 0)
        self.gridLayout.addWidget(self.logWidget, 0, 1)
        
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