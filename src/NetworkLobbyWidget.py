from PyQt4 import QtGui, QtCore

class NetworkLobbyWidget(QtGui.QWidget):
#Provides a list of availabe network games and peers
#User can click a game to join
#Callbacks can be used to add or remove games and peers
    def __init__(self, win_parent = None):
        QtGui.QWidget.__init__(self, win_parent)
        
        layout = QtGui.QVBoxLayout()
        
        self.gameList = QtGui.QListWidget(self)
        self.peerList = QtGui.QListWidget(self)
        self.playerList = QtGui.QListWidget(self)
        
        self.gameList.itemDoubleClicked.connect(self.gameDoubleClicked)
        
        label = QtGui.QLabel("Active games: ", self)
        addButton = QtGui.QPushButton("Add", self)
        addButton.clicked.connect(self.addGameClicked)
        
        label2 = QtGui.QLabel("Active peers: ", self)
        label3 = QtGui.QLabel("Active players: ", self)
        
        layout.addWidget(label)
        layout.addWidget(self.gameList)
        layout.addWidget(addButton)
        layout.addWidget(label2)
        layout.addWidget(self.peerList)
        layout.addWidget(label3)
        layout.addWidget(self.playerList)
        
        self.setLayout(layout)
        
    def addGameClicked(self):
        print "game add clicked"
        self.emit(QtCore.SIGNAL("addGame()"))
        
    def addGame(self, game, UUID):
        # Callback to add a game with name and UUID to the list.
        lobbyItem = NetworkLobbyGameItem(game['name'], self.gameList, UUID, game)
        self.gameList.addItem(lobbyItem)
    
    
    def removeGame(self, UUID):
        # Callback to remove a game with name and UUID from the list.
        for i in range(self.gameList.count()):
            currentItem = self.gameList.item(i)
            if(currentItem.UUID == UUID):
                self.gameList.removeItemWidget(currentItem)
                break
            
    def getGameInfo(self, UUID):
        for i in range(self.gameList.count()):
            currentItem = self.gameList.item(i)
            if(currentItem.UUID == UUID):
                return {'rows' : currentItem.numRows, 'cols' : currentItem.numCols, 'name' : currentItem.gameName, 'comment' : currentItem.gameComment, 'waitTime' : currentItem.waitTime, 'UUID': UUID}
            
    def addPeer(self, serviceName, interfaceIndex, ip, port):
        newItem = NetworkLobbyPeerItem(serviceName, serviceName, interfaceIndex, ip, port, self.peerList)
        self.peerList.addItem(newItem)
        
    
    def removePeer(self, serviceName, interfaceIndex):
        for i in range(self.peerList.count()):
            currentItem = self.peerList.item(i)
            if(currentItem.serviceName == serviceName and currentItem.interfaceIndex == interfaceIndex):
                self.peerList.removeItemWidget(currentItem)
                break
            
    def addPlayer(self, player):
        newItem = NetworkLobbyPlayerItem(player.name, player, self.playerList)
        self.playerList.addItem(newItem)
        
    def updatePlayer(self, player):
        for i in range(self.playerList.count()):
            currentItem = self.playerList.item(i)
            if(currentItem.player.UUID == player.UUID):
                currentItem.setPlayer(player)
                break
    
    def removePlayer(self, player):
        for i in range(self.playerList.count()):
            currentItem = self.playerList.item(i)
            if(currentItem.player.UUID == player.UUID):
                self.peerList.removeItemWidget(currentItem)
                break
        
    
    def gameDoubleClicked(self, item):
        # Called when the user doubleclicks an item in the list. The game clicked should be joined.
        print "double clicked"
        UUID = item.UUID
        name = item.text()
        print "UUID: " + str(UUID)
        
        self.emit(QtCore.SIGNAL("joinGameClicked(PyQt_PyObject, QString)"), UUID, name)
    
    
    
class NetworkLobbyGameItem(QtGui.QListWidgetItem):
    # Used as an item in the lobby list. An item contains the UUID of a particular game and makes it visible in the GUI
    def __init__(self, text, view, UUID, game):
        QtGui.QListWidgetItem.__init__(self, text, view)
        
        self.setToolTip(str("description: " + str(game['description']) + "\nRows: " + str(game['numRows']) + "\nCols: " + str(game['numCols']) + "\nWait time: " + str(game['waitTime']) + "\nStart time: " + str(game['starttime'])))
        
        self.UUID = UUID
        self.gameName = text
        self.gameComment = str(game['description'])
        self.numRows = game['numRows']
        self.numCols = game['numCols']
        self.waitTime = game['waitTime']
        self.startTime = game['starttime']
        

class NetworkLobbyPeerItem(QtGui.QListWidgetItem):
    # Used as an item in the lobby list. An item contains the UUID of a particular game and makes it visible in the GUI
    def __init__(self, text, serviceName, interfaceIndex, ip, port, view):
        QtGui.QListWidgetItem.__init__(self, text, view)
        
        self.setToolTip(str("Interfaceindex: " + str(interfaceIndex) + "\nip: " + str(ip) + "\nport: " + str(port)))
        
        self.serviceName = serviceName
        self.interfaceIndex = interfaceIndex
        self.ip = ip
        self.port = port
        
class NetworkLobbyPlayerItem(QtGui.QListWidgetItem):
    def __init__(self, text, player, view):
        QtGui.QListWidgetItem.__init__(self, text, view)
        
        self.player = player
    def setPlayer(self, player):
        self.setText(player.name)
        self.setToolTip(str("UUID: " + player.UUID + "\ncolor: " + str(player.color)))