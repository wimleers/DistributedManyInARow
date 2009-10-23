from PyQt4 import QtGui, QtCore
import sys

class MainWindow(QtGui.QMainWindow):
    def __init__(self, win_parent = None):
        QtGui.QMainWindow.__init__(self, win_parent)
        
        
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    app.exec_()