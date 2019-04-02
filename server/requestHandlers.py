def handshake(message, self, peers):
    """no peersLock, should be thread safe because only a thread is in charge of a peer"""

    peerID = message.split()[1]
    self.peerID = peerID

    if peerID in peers:
        """"peers already discovered in a previous session"""
        peers[peerID]["peerIP"] = self.client_addr[0]
        peers[peerID]["peerPort"] = self.client_addr[1]
    else:
        """unknown peer"""
        peers[peerID] = dict()
        peers[peerID]["peerIP"] = self.client_addr[0]
        peers[peerID]["peerPort"] = self.client_addr[1]

    message = "HELLO {}".format(peerID)
    self.client_sock.send(message.encode('ascii'))

def hideGroupInfo(group):
    """"This function return a group dictionary without the token fields and without the list of peers"""
    modGroup = dict()
    modGroup["name"] = group["name"]
    modGroup["total"] = group["total"]
    modGroup["active"] = group["active"]
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

    groupName = message.split()[2]
    if groupName in groups:
            if self.peerID in groups[groupName]["peers"]:
                groups[groupName]["peers"][self.peerID]["active"] = True
                answer = "GROUP {} RESTORED".format(groupName)
            else:
                answer = "IT'S NOT POSSIBLE TO RESTORE GROUP {}, PEER DOESN'T BELONG TO IT".format(groupName)
    else:
        answer = "IT'S NOT POSSIBLE TO RESTORE GROUP {}, GROUP DOESN'T EXIST".format(groupName)

    self.client_sock.send(answer.encode('ascii'))

def joinGroup(message, self, groups, peers):
    """"make the user active in a new group group
    choosing also the role as function of the token provided"""

    groupName = message.split()[2]
    tokenProvided = message.split()[4]

    if groupName in groups:
        if tokenProvided == groups[groupName]["tokenRW"]:
            groups[groupName]["peers"][self.peerID] = dict()
            groups[groupName]["peers"][self.peerID]["peerID"] = peerID
            groups[groupName]["peers"][self.peerID]["role"] = "RW"
            groups[groupName]["peers"][self.peerID]["active"] = True
        elif tokenProvided == groups[groupName]["tokenRO"]:
            groups[groupName]["peers"][self.peerID] = dict()
            groups[groupName]["peers"][self.peerID]["peerID"] = peerID
            groups[groupName]["peers"][self.peerID]["role"] = "RO"
            groups[groupName]["peers"][self.peerID]["active"] = True
            groups[groupName]["peers"][self.peerID]["active"] = True
        else:
            answer = "IMPOSSIBLE TO JOIN GROUP {} - WRONG TOKEN".format(groupName)
    else:
        answer = "IMPOSSIBLE TO JOIN GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    self.client_sock.send(answer.encode('ascii'))

def createGroup(message, self, group, peers):
    pass