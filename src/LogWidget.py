from PyQt4 import QtGui, QtCore
import sys

class LogWidget(QtGui.QListWidget):
    def __init__(self, win_parent = None):
        QtGui.QListWidget.__init__(self, win_parent)
        
        self.setMaximumWidth(200)
        
    
    def addMessage(self, player, message):
        time = QtCore.QTime.currentTime().toString()
        newItem = QtGui.QListWidgetItem(time + ": " + player.name + ": " + message, self)
        newItem.setBackgroundColor(QtGui.QColor(player.color[0], player.color[1], player.color[2]))
        self.addItem(newItem)