"""
Project: myP2PSync
Code for server-side groups management.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""


class Group:
    """
    Class for a single group management.
    It contains all the information regarding a group,
    including the list of peers and the list of files.
    """

    def __init__(self, name, tokenRW, tokenRO):
        """
        Initialize group parameters.
        :param name: name of the group
        :param tokenRW: token for RW privilege
        :param tokenRO: token for RO privilege
        """
        self.name = name
        self.tokenRW = tokenRW
        self.tokenRO = tokenRO
        self.activePeers = 0
        self.totalPeers = 0
        self.nrFiles = 0

        # Data structure for storing peers info for the group
        # key: peerID
        # value: PeerInGroup object
        self.peersInGroup = dict()

        # Data structure for storing filess info for the group
        # key: filename e.g. file.txt or dir1/dir2/file.txt
        # the second version allows directories handling
        # value: FileInGroup object
        self.filesInGroup = dict()

    def addPeer(self, peerID, active, role):
        """
        Add a peer to a group.
        :param peerID: id of the peer
        :param active: boolean value
        :param role: role of the peer
        :return: void
        """
        p = PeerInGroup(peerID, active, role)
        self.peersInGroup[peerID] = p
        if active:
            self.activePeers += 1
        self.totalPeers += 1

    def restorePeer(self, peerID):
        """
        Restore a peer putting Active = True.
        :param peerID: id of the peer
        :return: void
        """
        self.peersInGroup[peerID].active = True
        self.activePeers += 1

    def removePeer(self, peerID):
        """
        Remove a peer from the group.
        :param peerID: id of the peer
        :return: void
        """
        if self.peersInGroup[peerID].active:
            self.activePeers -= 1
        self.totalPeers -= 1
        del self.peersInGroup[peerID]

    def disconnectPeer(self, peerID):
        """
        Disconnect a peer putting Active = False.
        :param peerID: id of the peer
        :return: void
        """
        self.peersInGroup[peerID].active = False
        self.activePeers -= 1

    def addFile(self, filename, filesize, timestamp):
        """
        Add a file to a group.
        :param filename: filename string
        :param filesize: filesize value
        :param timestamp: timestamp value
        :return: void
        """
        f = FileInGroup(filename, filesize, timestamp)
        self.filesInGroup[filename] = f
        self.nrFiles += 1

    def updateFile(self, filename, filesize, timestamp):
        """
        Update file info.
        :param filename: filename string
        :param filesize: new filesize value
        :param timestamp: new timestamp value
        :return: void
        """
        try:
            self.filesInGroup[filename].filesize = filesize
            self.filesInGroup[filename].timestamp = int(timestamp)
        except KeyError:
            pass

    def removeFile(self, filename):
        """
        Remove file from a group.
        :param filename: filename string
        :return: void
        """
        try:
            del self.filesInGroup[filename]
            self.nrFiles -= 1
        except KeyError:
            pass

    def getPublicInfo(self):
        """
        Return a dictionary containing public group information.
        Tokens are considerate private information.
        :return: a dictionary
        """
        groupInfo = dict()
        groupInfo["name"] = self.name
        groupInfo["total"] = self.totalPeers
        groupInfo["active"] = self.activePeers
        return groupInfo


class PeerInGroup:
    """
    Class describing a peer into a group.
    """

    def __init__(self, peerID, active, role):
        """
        Initialize peer information
        :param peerID: id of the peer
        :param active: peer's status (boolean)
        :param role: peer's role
        """
        self.peerID = peerID
        self.active = active
        self.role = role


class FileInGroup:
    """
    Class describing a file into a group.
    """

    def __init__(self, filename, filesize, timestamp):
        """
        Initialize file information.
        :param filename: filename string
        :param filesize: filesize value
        :param timestamp: timestamp value
        """
        self.filename = filename
        self.filesize = filesize
        self.timestamp = int(timestamp)
