from PyQt4 import QtGui, QtCore
import sys

class LogWidget(QtGui.QListWidget):
    def __init__(self, win_parent = None):
        QtGui.QListWidget.__init__(self, win_parent)
        
        self.setMaximumWidth(200)
        
    
    def addMessage(self, color, message):
        time = QtCore.QTime.currentTime().toString()
        newItem = QtGui.QListWidgetItem(time + ": " + message, self)
        newItem.setBackgroundColor(color)
        self.addItem(newItem)
        
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wid = LogWidget()
    wid.addMessage(QtGui.QColor(255, 0, 0), "Player 1 at location( 1, 2 )")
    wid.addMessage(QtGui.QColor(0, 255, 0), "Player 2 at location( 2, 1 )")
    wid.addMessage(QtGui.QColor(0, 0, 255), "Player 3 at location( 3, 1 )")
    
    wid.show()
    app.exec_()