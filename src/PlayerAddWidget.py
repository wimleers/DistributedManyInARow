from PyQt4 import QtGui, QtCore
import PyQt4.uic
import sys

class PlayerAddWidget(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        
        self.createLayout()
        
    def createLayout(self):
        self.gridLayout = QtGui.QGridLayout(self)
        label1 = QtGui.QLabel("<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">" +
        "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">" + 
        "p, li { white-space: pre-wrap; }" +
        "</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">" +
        "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:16pt;\">Your details:</span></p></body></html>", self)
        label2 = QtGui.QLabel("Name: ", self)
        
        self.gridLayout.addWidget(label1, 0, 0, 1, 2)
        self.gridLayout.addWidget(label2, 1, 0)
        
        self.nameEdit = QtGui.QLineEdit(self)
        self.gridLayout.addWidget(self.nameEdit, 1, 1)
        
        saveButton = QtGui.QPushButton("Save", self)
        saveButton.clicked.connect(self.saveData)
        
        self.gridLayout.addWidget(saveButton, 3, 0)
        
    def saveData(self):
        self.name = self.nameEdit.text()
        if(self.name.size() == 0):
            QtGui.QMessageBox.warning(self, "Error", "You have to enter a name.")
            return
        
        self.accept()
        
    def getPlayerInfo(self):
        self.exec_()
        
        if(self.result() == 1):
            return self.name
        else:
            return None
        
    def reject(self):
        self.close()
        
    def closeEvent(self, event):
        QtGui.QMessageBox.warning(self, "Error", "You have to enter a name.")
        event.ignore()
        