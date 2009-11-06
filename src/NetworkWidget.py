from PyQt4 import QtGui, QtCore
from Neighborhood import *
import sys
import platform

class NetworkWidget(QtGui.QDialog):
    def __init__(self, win_parent = None):
        QtGui.QDialog.__init__(self, win_parent)
        
        self.createLayout()
        self.listenOnly = False
        self.services = []
        
        self.gameList.itemDoubleClicked.connect(self.loadGame)
        
        self.launchNeighborhoodDiscovery()
        
    def closeEvent(self, event):
        self.neighborhood.kill()
        
    def launchNeighborhoodDiscovery(self):
        # Initialize the neighborhood.
        port = 4444
        if self.listenOnly:
            port = 4445
        self.neighborhood = Neighborhood(serviceName = platform.node(),
                         serviceType = '_manyinarow._tcp',
                         protocolVersion = 1,
                         port = port,
                         serviceRegistrationCallback=self.serviceRegistrationCallback,
                         serviceRegistrationErrorCallback=self.serviceRegistrationErrorCallback,
                         peerServiceDiscoveryCallback=self.peerServiceDiscoveryCallback,
                         peerServiceRemovalCallback=self.peerServiceRemovalCallback,
                         peerServiceUpdateCallback=self.peerServiceUpdateCallback,
                         peerMessageCallback=self.peerMessageCallback)
        
        self.neighborhood.start()
        
    def createLayout(self):
        self.layout = QtGui.QGridLayout(self)
        self.gameList = QtGui.QListWidget(self)
        self.layout.addWidget(self.gameList, 1, 0)
        
        label = QtGui.QLabel("The following games are active: ")
        self.layout.addWidget(label, 0, 0)
        
    def updateNetworkGames(self):
        print "updating"
        self.gameList.clear()
        for game in self.services:
            self.gameList.addItem(game["serviceName"])
            
    def loadGame(self, item):
        #todo: add code to signal back-end to connect to the selected game (in item text)
        print item.text()
        self.accept()
        #self.emit(bleeeh)
        
        
    #Callback functions for Neighbourhood service discovery:
    def serviceRegistrationCallback(self, sdRef, flags, errorCode, name, regtype, domain):
        print "SERVICE REGISTRATION CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, name=%s, regtype=%s, domain=%s" % (sdRef.fileno(), flags, errorCode, name, regtype, domain)

    def serviceRegistrationErrorCallback(self, sdRef, flags, errorCode, errorMessage, name, regtype, domain):
        print "SERVICE REGISTRATION ERROR CALLBACK FIRED, params: sdRef=%d, flags=%d, errorCode=%d, errorMessage=%s, name=%s, regtype=%s, domain=%s" % (sdRef, flags, errorCode, errorMessage, name, regtype, domain)

    def peerServiceDiscoveryCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        self.services[(serviceName, interfaceIndex)] = {"serviceName": serviceName, "interfaceIndex": interfaceIndex, "fullname": fullname, "hosttarget": hosttarget, "ip": ip, "port": port}
        print "SERVICE DISCOVERY CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

    def peerServiceRemovalCallback(self, serviceName, interfaceIndex):
        self.services.remove((services, interfaceIndex))
        print "SERVICE REMOVAL CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d" % (serviceName, interfaceIndex)

    def peerServiceUpdateCallback(self, serviceName, interfaceIndex, fullname, hosttarget, ip, port):
        print "SERVICE UPDATE CALLBACK FIRED, params: serviceName=%s, interfaceIndex=%d, fullname=%s, hosttarget=%s, ip=%s, port=%d" % (serviceName, interfaceIndex, fullname, hosttarget, ip, port)

    def peerMessageCallback(self, serviceName, interfaceIndex, txtRecords, updated, deleted):
        print "PEER MESSAGE CALLBACK FIRED", serviceName, interfaceIndex, txtRecords
        print "\tupdated:"
        for key in updated:
            print "\t\t", key, txtRecords[key]
        print "\tdeleted:"
        for key in deleted:
            print "\t\t", key
            
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    wid = NetworkWidget()
    
    wid.exec_()