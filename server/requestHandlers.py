def handshake(message, self, peers):
    """no peersLock, should be thread safe because only a thread is in charge of a peer"""

    peerID = message.split()[1]
    self.peerID = peerID

    if peerID in peers:
        peers[peerID]["peerIP"] = self.client_addr[0]
        peers[peerID]["peerPort"] = self.client_addr[1]
    else:
        peers[peerID] = dict()
        peers[peerID]["peerIP"] = self.client_addr[0]
        peers[peerID]["peerPort"] = self.client_addr[1]
        peers[peerID]["groups"] = list()

    message = "HELLO {}".format(peerID)
    self.client_sock.send(message.encode('ascii'))

def hideGroupInfo(group):
    """"This function return a group dictionary without the token fields and without the list of peers"""
    modGroup = group
    del modGroup["tokenRW"]
    del modGroup["tokenRO"]
    del modGroup["peers"]
    return modGroup


def sendList(self, groups, previous):
    """This function can retrieve the list of previous (already joined, previous=True) groups
    or the list of not-joined groups (previous = False) for a certain peerID"""
    groupList = list()

    for g in groups.values():
        if self.peerID in g["peers"] and previous:
            groupList.append(hideGroupInfo(g))
            continue
        if self.peerID not in g["peers"] and not previous:
            groupList.append(hideGroupInfo(g))

    self.client_sock.send(str(groupList).encode('ascii'))

def restoreGroup(message, self, groups):
    """"make the user active in one of its group"""

    groupName = message.split()[1]
    #if groupName in groups and groupName in peers[self.peerID][groups]:


def joinGroup(message, self, groups, peers):
    request = message.rstrip().split()
    print(request)
    groupName = request[1]
    groupToken = request[3]

    if groupName in groupDict:
        if groupDict[groupName] == groupToken:
            message = "GROUP JOINED"
        else:
            message = "ACCESS DENIED"
    else:
        message = "ACCESS DENIED"

    sock.send(message.encode('ascii'))

def createGroup(message, self, group, peers):
    pass