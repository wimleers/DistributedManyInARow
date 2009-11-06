from PyQt4 import QtGui, QtCore
from Neighborhood import *
import sys
import platform

class NetworkWidget(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        
        self.createLayout()
        
        self.gameList.itemDoubleClicked.connect(self.startGame)

    def createLayout(self):
        self.layout = QtGui.QGridLayout(self)
        self.gameList = QtGui.QListWidget(self)
        self.layout.addWidget(self.gameList, 1, 0)
        
        label = QtGui.QLabel("The following games were found: ")
        self.layout.addWidget(label, 0, 0)
        
    def updateNetworkGames(self, games):
        print "updating"
        self.gameList.clear()
        for game in games:
            self.gameList.addItem(game)
            
    def startGame(self, item):
        #todo: add code to signal back-end to connect to the selected game (in item text)
        print item.text()
        self.accept()
        #self.emit(bleeeh)
            
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wid = NetworkWidget()
    
    wid.exec_()