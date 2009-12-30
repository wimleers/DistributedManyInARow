from PyQt4 import QtGui, QtCore
import sys

#defines the size for a square in the field
SIZE = 50
#defines the size of the circles in the field
CIRCLESIZE = 45

class GraphicsScene(QtGui.QGraphicsScene):
    def __init__(self, nrRows, nrCols, color, win_parent = None):
        QtGui.QGraphicsScene.__init__(self, win_parent)
        
        self.nrRows = nrRows
        self.nrCols = nrCols
        #contains the column number of the column where the mouse is at
        self.currentHoverIndex = -1
        
        self.setupDefaultBoard(nrRows, nrCols)
        self.setupTempBlock(nrRows, nrCols, color)
        
        self.waitText = QtGui.QGraphicsTextItem()
        self.waitText = self.addText("...Please wait...")
        self.waitText.setZValue(100)
        self.freezeText = QtGui.QGraphicsTextItem()
        self.freezeText = self.addText("...Game frozen...")
        self.freezeText.setZValue(100)
        font = QtGui.QFont()
        font.setBold(True)
        font.setFamily("Comic Sans MS")
        font.setPointSize(30)
        self.waitText.setFont(font)
        self.freezeText.setFont(font)
        self.waitText.setDefaultTextColor(QtGui.QColor(0,0,255))
        self.freezeText.setDefaultTextColor(QtGui.QColor(0,0,255))
        sceneSize = self.sceneRect()
        midx = (sceneSize.width() / 2) - (self.waitText.boundingRect().width() / 2)
        midy = (sceneSize.height() / 2) - (self.waitText.boundingRect().height() / 2)
        self.waitText.setPos(midx, midy)
        midx = (sceneSize.width() / 2) - (self.freezeText.boundingRect().width() / 2)
        midy = (sceneSize.height() / 2) - (self.freezeText.boundingRect().height() / 2)
        self.freezeText.setPos(midx, midy)
        self.waitText.hide()
        self.freezeText.hide()
        
        self.rejectClicks = False

        
    def block(self, freeze):
        self.setForegroundBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50, 180)))
        if(freeze):
            self.freezeText.show()
        else:
            self.waitText.show()
        self.rejectClicks = True
    
    def unblock(self, freeze):
        if(self.freezeText.isVisible() and not freeze):
            self.waitText.hide()
            return
        self.setForegroundBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        if(freeze):
            self.freezeText.hide()
        else:
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
        
    def setupTempBlock(self, nrRows, nrCols, color):
        #contains the item that shows where the next block will fall:
        
        self.tempItem = QtGui.QGraphicsEllipseItem(0 + (SIZE - CIRCLESIZE)/2, nrRows-1 + (SIZE - CIRCLESIZE)/2, CIRCLESIZE, CIRCLESIZE)
        
        self.radialGrad = QtGui.QRadialGradient(0 + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, nrRows-1 + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, CIRCLESIZE/2)
        self.radialGrad.setColorAt(0, color)
        #radialGrad.setColorAt(0.45, QtGui.QColor(255,255,255))
        self.radialGrad.setColorAt(1, QtGui.QColor(255,255,255))
        brush = QtGui.QBrush(self.radialGrad)
       
        pen = QtGui.QPen(QtCore.Qt.NoPen)
        
        self.tempItem.setPen(pen)
        self.tempItem.setBrush(brush)
        self.tempItem.setZValue(2)

        self.addItem(self.tempItem)
        self.tempItem.hide()
    
    def makeMove(self, xpos, ypos, color):
        self.currentHoverIndex = -1
        self.tempItem.hide()
        
        rectItem = self.gameBoard[xpos][ypos]
        x = rectItem.rect().x()
        y = rectItem.rect().y()
        
        xpos = x + (SIZE - CIRCLESIZE)/2
        ypos = y + (SIZE - CIRCLESIZE)/2
        
        circleItem = QtGui.QGraphicsEllipseItem(xpos, ypos, CIRCLESIZE, CIRCLESIZE)
        
        xpos = x + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2
        ypos = y + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2
        
        radialGrad = QtGui.QRadialGradient(xpos, ypos, CIRCLESIZE/2)
        radialGrad.setColorAt(0, color)
        radialGrad.setColorAt(0.45, color)
        radialGrad.setColorAt(1, QtGui.QColor(255,255,255))
        brush = QtGui.QBrush(radialGrad)
       
        pen = QtGui.QPen(QtCore.Qt.NoPen)
        
        circleItem.setPen(pen)
        circleItem.setBrush(brush)
        circleItem.setZValue(3)
        
        self.addItem(circleItem)
        
    def makeDummyMove(self, columnIndex, rowIndex, color):
        self.tempItem.hide()

        rectItem = self.gameBoard[columnIndex][rowIndex]
        x = rectItem.rect().x()
        y = rectItem.rect().y()
        
        xpos = x + (SIZE - CIRCLESIZE)/2
        ypos = y + (SIZE - CIRCLESIZE)/2
        
        self.tempItem.setRect(xpos, ypos, CIRCLESIZE, CIRCLESIZE)
        
        self.radialGrad = QtGui.QRadialGradient(x + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, y + (CIRCLESIZE/2) + (SIZE - CIRCLESIZE)/2, CIRCLESIZE/2)
        self.radialGrad.setColorAt(0, color)
        #radialGrad.setColorAt(0.45, QtGui.QColor(255,255,255))
        self.radialGrad.setColorAt(1, QtGui.QColor(255,255,255))
        brush = QtGui.QBrush(self.radialGrad)
       
        pen = QtGui.QPen(QtCore.Qt.NoPen)
        
        self.tempItem.setPen(pen)
        self.tempItem.setBrush(brush)
        self.tempItem.setZValue(2)
        
        self.tempItem.show()
        
    def mousePressEvent(self, event):
        self.tempItem.hide()
        # Only accept a move when the gameboard is enabled
        if(not self.rejectClicks):
            item = self.itemAt(event.scenePos())
            for i in range(self.nrCols):
                for j in range(self.nrRows):
                    if(self.gameBoard[i][j] == item):
                        self.emit(QtCore.SIGNAL("playerClicked(int)"), i)
                    
    def mouseDoubleClickEvent(self, event):
        self.tempItem.hide()
        #this enables the user to click rapidly
        if(not self.rejectClicks):
            item = self.itemAt(event.scenePos())
            for i in range(self.nrCols):
                for j in range(self.nrRows):
                    if(self.gameBoard[i][j] == item):
                        self.emit(QtCore.SIGNAL("playerClicked(int)"), i)
                    
    def mouseMoveEvent(self, event):
        item = self.itemAt(event.scenePos())
        if(not self.rejectClicks):
            self.tempItem.show()
            for i in range(self.nrCols):
                for j in range(self.nrRows):
                    if(self.gameBoard[i][j] == item):
                        if(i != self.currentHoverIndex):
                            self.currentHoverIndex = i
                            self.emit(QtCore.SIGNAL("mouseHoverColumn(int)"), i)
                        