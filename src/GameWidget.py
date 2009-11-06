from PyQt4 import QtGui, QtCore
from PyQt4 import uic
from GraphicsScene import GraphicsScene
from LogWidget import LogWidget

class GameWidget(QtGui.QWidget):
#GameWidget provides a window in which a game can be played. It displays the gameboard(GraphicsScene),
#active players, log messages and chat messages
    def __init__(self, nrRows, nrCols, gameUUID, win_parent = None):
        QtGui.QWidget.__init__(self, win_parent)
        
        self.nrRows = nrRows
        self.nrCols = nrCols
        self.gameUUID = gameUUID
        self.createLayout()
        
    def getGameUUID(self):
        return self.gameUUID
        
    def createLayout(self):
        self.ui = uic.loadUi("GameWidget.ui", self)
        self.scene = GraphicsScene(self.nrRows, self.nrCols, self)
        self.ui.graphicsView.setScene(self.scene)
        self.logList = LogWidget(self)
        self.logList.setMaximumSize(250, 200)
        self.ui.verticalLayout.addWidget(self.logList)
        self.ui.show()