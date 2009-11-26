from PyQt4 import QtGui, QtCore
import sys

#defines the size for a square in the field
SIZE = 50
#defines the size of the circles in the field
CIRCLESIZE = 45

class GraphicsScene(QtGui.QGraphicsScene):
    def __init__(self, nrRows, nrCols, win_parent = None):
        QtGui.QGraphicsScene.__init__(self, win_parent)
        
        self.nrRows = nrRows
        self.nrCols = nrCols
        #contains the column number of the column where the mouse is at
        self.currentHoverIndex = -1
        #contains the item that shows where the next block will fall:
        self.tempItem = None
        
        self.setupDefaultBoard(nrRows, nrCols)
        
        self.waitText = QtGui.QGraphicsTextItem()
        self.waitText = self.addText("...Please wait...")
        font = QtGui.QFont()
        font.setBold(True)
        font.setFamily("Comic Sans MS")
        font.setPointSize(30)
        self.waitText.setFont(font)
        self.waitText.setDefaultTextColor(QtGui.QColor(0,0,255))
        sceneSize = self.sceneRect()
        midx = (sceneSize.width() / 2) - (self.waitText.boundingRect().width() / 2)
        midy = (sceneSize.height() / 2) - (self.waitText.boundingRect().height() / 2)
        self.waitText.setPos(midx, midy)
        self.waitText.hide()
        
        self.rejectClicks = False

        
    def block(self):
        self.setForegroundBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50, 180)))
        self.waitText.show()
        self.rejectClicks = True
    
    def unblock(self):
        self.setForegroundBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        self.waitText.hide()
        self.rejectClicks = False
        
    def setupDefaultBoard(self, nrRows, nrCols):
        self.gameBoard = [[QtGui.QGraphicsRectItem for i in xrange(nrRows)] for j in xrange(nrCols)]
        for i in range(nrCols):
            for j in range(nrRows):
                rectItem = QtGui.QGraphicsRectItem(i*SIZE, j*SIZE, SIZE, SIZE)
                self.addItem(rectItem)
                self.gameBoard[i][j] = rectItem
                
        self.setSceneRect(-10, -10, nrCols * SIZE +20, nrRows * SIZE + 20)
        
    
    def makeMove(self, xpos, ypos, color):
        if(self.tempItem != None):
            self.removeItem(self.tempItem)
        rectItem = self.gameBoard[xpos][ypos]
        x = rectItem.rect().x()
        y = rectItem.rect().y()
        
        circleItem = QtGui.QGraphicsEllipseItem(x + (SIZE - CIRCLESIZE)/2, y + (SIZE - CIRCLESIZE)/2, CIRCLESIZE, CIRCLESIZE)
        
        radialGrad = QtGui.QRadialGradient(x + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, y + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, CIRCLESIZE/2)
        radialGrad.setColorAt(0, color)
        radialGrad.setColorAt(0.45, color)
        radialGrad.setColorAt(1, QtGui.QColor(255,255,255))
        brush = QtGui.QBrush(radialGrad)
       
        pen = QtGui.QPen(QtCore.Qt.NoPen)
        
        circleItem.setPen(pen)
        circleItem.setBrush(brush)
        
        self.addItem(circleItem)
        
    def makeDummyMove(self, columnIndex, rowIndex, color):
        if(self.tempItem != None):
            self.removeItem(self.tempItem)

        rectItem = self.gameBoard[columnIndex][rowIndex]
        x = rectItem.rect().x()
        y = rectItem.rect().y()
        
        self.tempItem = QtGui.QGraphicsEllipseItem(x + (SIZE - CIRCLESIZE)/2, y + (SIZE - CIRCLESIZE)/2, CIRCLESIZE, CIRCLESIZE)
        radialGrad = QtGui.QRadialGradient(x + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, y + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, CIRCLESIZE/2)
        radialGrad.setColorAt(0, color)
        #radialGrad.setColorAt(0.45, QtGui.QColor(255,255,255))
        radialGrad.setColorAt(1, QtGui.QColor(255,255,255))
        brush = QtGui.QBrush(radialGrad)
       
        pen = QtGui.QPen(QtCore.Qt.NoPen)
        
        self.tempItem.setPen(pen)
        self.tempItem.setBrush(brush)
        
        self.addItem(self.tempItem)
        
    def mousePressEvent(self, event):
        # Only accept a move when the gameboard is enabled
        if(not self.rejectClicks):
            item = self.itemAt(event.scenePos())
            for i in range(self.nrCols):
                for j in range(self.nrRows):
                    if(self.gameBoard[i][j] == item):
                        self.emit(QtCore.SIGNAL("playerClicked(int)"), i)
                    
    def mouseDoubleClickEvent(self, event):
        #this enables the user to click rapidly
        if(not self.rejectClicks):
            item = self.itemAt(event.scenePos())
            for i in range(self.nrCols):
                for j in range(self.nrRows):
                    if(self.gameBoard[i][j] == item):
                        self.emit(QtCore.SIGNAL("playerClicked(int)"), i)
                    
    def mouseMoveEvent(self, event):
        item = self.itemAt(event.scenePos())
        for i in range(self.nrCols):
            for j in range(self.nrRows):
                if(self.gameBoard[i][j] == item):
                    if(i != self.currentHoverIndex):
                        self.currentHoverIndex = i
                        self.emit(QtCore.SIGNAL("mouseHoverColumn(int)"), i)
                        

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = QtGui.QGraphicsView()
    scene = GraphicsScene(13, 10, view)
    scene.makeMove(0, 12, QtGui.QColor(10, 20, 255))
    scene.makeMove(3, 12, QtGui.QColor(10, 255, 255))
    scene.makeMove(4, 12, QtGui.QColor(255, 20, 0))
    scene.makeMove(7, 12, QtGui.QColor(10, 255, 70))
    scene.makeMove(9, 12, QtGui.QColor(90, 115, 200))
    view.setScene(scene)
    view.show()
    app.exec_()