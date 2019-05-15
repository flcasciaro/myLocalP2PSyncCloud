"""File containing classes for Group management of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""


class Group:

    def __init__(self, name, tokenRW, tokenRO):
        self.name = name
        self.tokenRW = tokenRW
        self.tokenRO = tokenRO
        self.activePeers = 0
        self.totalPeers = 0
        self.nrFiles = 0
        self.peersInGroup = dict()
        self.filesInGroup = dict()

    def addPeer(self, peerID, active, role):
        p = PeerInGroup(peerID, active, role)
        self.peersInGroup[peerID] = p
        if active:
            self.activePeers += 1
        self.totalPeers += 1

    def restorePeer(self, peerID):
        self.peersInGroup[peerID].active = True
        self.activePeers += 1

    def removePeer(self, peerID):
        #added because a peer can be eliminated from a master
        if self.peersInGroup[peerID].active:
            self.activePeers -= 1
        del self.peersInGroup[peerID]
        self.totalPeers -= 1

    def disconnectPeer(self, peerID):
        self.peersInGroup[peerID].active = False
        self.activePeers -= 1

    def addFile(self, filename, filesize, lastModifiedTime):
        f = FileInGroup(filename, filesize, lastModifiedTime)
        self.filesInGroup[filename] = f
        self.nrFiles += 1

    def updateFile(self, filename, filesize, lastModifiedTime):
        self.filesInGroup[filename].filesize = filesize
        self.filesInGroup[filename].lastModifiedTime = lastModifiedTime

    def removeFile(self, filename):
        del self.filesInGroup[filename]
        self.nrFiles -= 1

    def getPublicInfo(self, role):
        groupInfo = dict()
        groupInfo["name"] = self.name
        groupInfo["total"] = self.totalPeers
        groupInfo["active"] = self.activePeers
        groupInfo["role"] = role
        return groupInfo


class PeerInGroup:

    def __init__(self, peerID, active, role):
        self.peerID = peerID
        self.active = active
        self.role = role


class FileInGroup:

    def __init__(self, filename, filesize, lastModified):
        self.filename = filename
        self.filesize = filesize
        self.lastModified = lastModified

    def getFileInfo(self):
        fileInfo = dict()
        fileInfo["filename"] = self.filename
        fileInfo["filesize"] = self.filesize
        fileInfo["lastModified"] = self.lastModified
        return fileInfo


