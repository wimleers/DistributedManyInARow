from PyQt4 import QtGui, QtCore
import PyQt4.uic
import sys

class PlayerAddWidget(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        
        self.colorSet = False
        self.createLayout()
        
    def createLayout(self):
        self.gridLayout = QtGui.QGridLayout(self)
        label1 = QtGui.QLabel("<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">" +
        "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">" + 
        "p, li { white-space: pre-wrap; }" +
        "</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;\">" +
        "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:16pt;\">Your details:</span></p></body></html>", self)
        label2 = QtGui.QLabel("Name: ", self)
        label3 = QtGui.QLabel("Color: ", self)
        self.colorLabel = QtGui.QLabel("", self)
        self.colorLabel.setMinimumWidth(20)
        self.colorLabel.setMaximumWidth(100)
        self.colorLabel.setAutoFillBackground(True)
        
        self.gridLayout.addWidget(label1, 0, 0, 1, 2)
        self.gridLayout.addWidget(label2, 1, 0)
        self.gridLayout.addWidget(label3, 2, 0)
        self.gridLayout.addWidget(self.colorLabel, 2, 2)
        
        self.nameEdit = QtGui.QLineEdit(self)
        self.colorButton = QtGui.QPushButton("Pick color", self)
        self.colorButton.clicked.connect(self.launchColorPicker)
        
        self.gridLayout.addWidget(self.nameEdit, 1, 1)
        self.gridLayout.addWidget(self.colorButton, 2, 1)
        
        saveButton = QtGui.QPushButton("Save", self)
        saveButton.clicked.connect(self.saveData)
        cancelButton = QtGui.QPushButton("Cancel", self)
        cancelButton.clicked.connect(self.reject)
        
        self.gridLayout.addWidget(saveButton, 3, 1)
        self.gridLayout.addWidget(cancelButton, 3, 2)
        
    def launchColorPicker(self):
        self.color = QtGui.QColorDialog.getColor()
        palette = QtGui.QPalette()
        palette.setColor(0, 10, self.color)
        self.colorLabel.setPalette(palette)
        self.colorSet = True
        
    def saveData(self):
        name = self.nameEdit.text()
        if(name.size() == 0 or not self.colorSet):
            QtGui.QMessageBox.warning(self, "Error", "Some fields were not filled in.")
            return
        #todo: pass data to back-end
        self.accept()
        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wid = PlayerAddWidget()
    wid.exec_()