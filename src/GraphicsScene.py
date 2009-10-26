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
        self.setupDefaultBoard(nrRows, nrCols)
        
    def setupDefaultBoard(self, nrRows, nrCols):
        self.gameBoard = [[QtGui.QGraphicsRectItem for i in xrange(nrCols)] for j in xrange(nrRows)]
        for i in range(nrCols):
            for j in range(nrRows):
                rectItem = QtGui.QGraphicsRectItem(i*SIZE, j*SIZE, SIZE, SIZE)
                self.addItem(rectItem)
                self.gameBoard[i][j] = rectItem
        
    
    def makeMove(self, xpos, ypos, color):
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
        
    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos())
        for i in range(self.nrCols):
            for j in range(self.nrRows):
                if(self.gameBoard[i][j] == item):
                    self.emit(QtCore.SIGNAL("playerClicked(int)"), i)
    
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = QtGui.QGraphicsView()
    scene = GraphicsScene(10, 10, view)
    scene.makeMove(0, 9, QtGui.QColor(10, 20, 255))
    scene.makeMove(3, 9, QtGui.QColor(10, 255, 255))
    scene.makeMove(4, 9, QtGui.QColor(255, 20, 0))
    scene.makeMove(7, 9, QtGui.QColor(10, 255, 70))
    scene.makeMove(9, 9, QtGui.QColor(90, 115, 200))
    view.setScene(scene)
    view.show()
    app.exec_()