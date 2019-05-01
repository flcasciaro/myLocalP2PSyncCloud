
class Group:

    def __init__(self, name, tokenRW, tokenRO, activeUsers, totalUsers):
        self.name = name
        self.tokenRW = tokenRW
        self.tokenRO = tokenRO
        self.activeUsers = int(activeUsers)
        self.totalUsers = int(totalUsers)
        self.peersInGroup = dict()

    def addPeer(self, peerID, active, role):
        p = PeerInGroup(peerID, active, role)
        self.peersInGroup[peerID] = p

    def getPublicInfo(self, role):
        groupInfo = dict()
        groupInfo["name"] = self.name
        groupInfo["total"] = self.totalUsers
        groupInfo["active"] = self.activeUsers
        groupInfo["role"] = role
        return groupInfo


class PeerInGroup:

    def __init__(self, peerID, active, role):
        self.peerID = peerID
        self.active = active
        self.role = role



