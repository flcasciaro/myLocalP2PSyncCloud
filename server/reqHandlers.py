""""This script contains function that will be invoked by the server's thread in order
to serve clients request"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

from groupClass import Group

def handshake(request, thread):
    """Add or update information (IP, Port) about a peer.
    No need for peersLock, should be thread safe because only a single
    thread is in charge of a specific peer"""

    thread.peerID = request.split()[1]
    request = "HELLO {}".format(thread.peerID)
    thread.client_sock.send(request.encode('ascii'))


def sendGroups(thread, groups, action):
    """This function can retrieve the list of active, previous or other groups for a certain peerID"""
    groupsList = dict()
    action = action.upper()

    if action == "ACTIVE":
        for g in groups.values():
            if thread.peerID in g.peersInGroup:
                if g.peersInGroup[thread.peerID].active:
                    role = g.peersInGroup[thread.peerID].role
                    groupsList[g.name] = g.getPublicInfo(role)

    elif action == "PREVIOUS":
        for g in groups.values():
            if thread.peerID in g.peersInGroup:
                if not g.peersInGroup[thread.peerID].active:
                    role = g.peersInGroup[thread.peerID].role
                    groupsList[g.name] = g.getPublicInfo(role)

    elif action == "OTHER":
        for g in groups.values():
            if thread.peerID not in g.peersInGroup:
                groupsList[g.name]= g.getPublicInfo("")

    thread.client_sock.send(str(groupsList).encode('ascii'))

def sendGroupInfo(request, thread, groups):
    groupName = request.split()[2]

    if thread.peerID in groups[groupName].peersInGroup:
        role = groups[groupName].peersInGroup[thread.peerID].role
    else:
        role = ""
    groupInfo = groups[groupName].getPublicInfo(role)

    thread.client_sock.send(str(groupInfo).encode('ascii'))



def restoreGroup(request, thread, groups):
    """"make the user active in one of its group (already joined)"""

    groupName = request.split()[2]
    if groupName in groups:
            if thread.peerID in groups[groupName].peersInGroup:
                if not groups[groupName].peersInGroup[thread.peerID].active: #if not already active
                    groups[groupName].restorePeer(thread.peerID)
                    answer = "OK - GROUP {} RESTORED".format(groupName)
                else:
                    answer = "ERROR: - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER ALREADY ACTIVE".format(groupName)
            else:
                answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER DOESN'T BELONG TO IT".format(groupName)
    else:
        answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    thread.client_sock.send(answer.encode('ascii'))

def joinGroup(request, thread, groups):
    """"make the user active in a new group group
    choosing also the role as function of the token provided"""

    groupName = request.split()[2]
    tokenProvided = request.split()[4]

    if groupName in groups:
        if tokenProvided == groups[groupName].tokenRW or tokenProvided == groups[groupName].tokenRO:
            if tokenProvided == groups[groupName].tokenRW:
                role = "RW"
                answer = "OK - GROUP {} JOINED IN ReadWrite MODE".format(groupName)
            elif tokenProvided == groups[groupName].tokenRO:
                role = "RO"
                answer = "OK - GROUP {} JOINED IN ReadOnly MODE".format(groupName)
            groups[groupName].addPeer(thread.peerID, True, role)

        else:
            answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - WRONG TOKEN".format(groupName)
    else:
        answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    thread.client_sock.send(answer.encode('ascii'))

def createGroup(request, thread, groups):
    """This function allows a peer to create a new synchronization group
    specifying the groupName and the tokens. The creator peer become also the master
    of the new group."""

    newGroupName = request.split()[2]
    newGroupTokenRW = request.split()[4]
    newGroupTokenRO = request.split()[6]

    if newGroupName not in groups:
        """create the new group and insert in the group dictionary"""

        newGroup = Group(newGroupName, newGroupTokenRW, newGroupTokenRO)
        newGroup.addPeer(thread.peerID, True, "Master")
        groups[newGroupName] = newGroup

        answer =  "OK - GROUP {} SUCCESSFULLY CREATED".format(newGroupName)
    else:
        answer =  "ERROR - IMPOSSIBLE TO CREATE GROUP {} - GROUP ALREADY EXIST".format(newGroupName)

    thread.client_sock.send(answer.encode('ascii'))

def manageRole(request, thread, groups, groupsLock):

    action = request.split()[1]
    modPeerID = request.split()[2]
    groupName = request.split()[4]

    if action == "CHANGE_MASTER":
        newRole = "Master"
    elif action == "ADD_MASTER":
        newRole = "Master"
    elif action == "MAKE_IT_RW":
        newRole = "RW"
    elif action == "MAKE_IT_RO":
        newRole = "RO"

    if groupName in groups:
        """check if both peerIDs actually belongs to the group"""
        if thread.peerID in groups[groupName].peersInGroup and modPeerID in groups[groupName].peersInGroup:
            if groups[groupName].peersInGroup[thread.peerID].role.upper() == "MASTER":

                groupsLock.acquire()
                groups[groupName].peersInGroup[modPeerID].role = newRole

                if action.upper() == "CHANGE_MASTER":
                    groups[groupName].peersInGroup[thread.peerID].role = "RW"

                groupsLock.release()
                answer = "OK - OPERATION ALLOWED"

            else:
                answer = "ERROR - OPERATION NOT ALLOWED"
        else:
            answer = "ERROR - OPERATION NOT ALLOWED"
    else:
        answer = "ERROR - GROUP {} DOESN'T EXIST".format(groupName)

    thread.client_sock.send(answer.encode('ascii'))

def retrievePeers(request, thread, groups, peers):
    """"retrieve a list of peers (only active or all) for a specific group
    request format: "PEERS <GROUPNAME> <ACTIVE/ALL>"   """

    groupName = request.split()[1]
    selectAll = True if request.split()[2].upper() == "ALL" else False

    if groupName in groups:
        peersList = list()
        for peer in groups[groupName].peersInGroup:
            """skip inactive peers if selectAll is False"""
            if not groups[groupName].peersInGroup[peer].active and not selectAll:
                continue
            """skip the peer which made the request"""
            if peer == thread.peerID:
                continue
            peerInfo = dict()
            peerInfo["peerID"] = peer
            peerInfo["peerIP"] = peers[peer]["peerIP"]
            peerInfo["peerPort"] = peers[peer]["peerPort"]
            peerInfo["active"] = groups[groupName].peersInGroup[peer].active
            peerInfo["role"] = groups[groupName].peersInGroup[peer].role
            peersList.append(peerInfo)
        answer = str(peersList)
    else:
        answer = "ERROR - GROUP {} DOESN'T EXIST".format(groupName)
    thread.client_sock.send(answer.encode('ascii'))


def imHere(request, thread, peers):

    """store IP address and Port Number on which the peer can be contacted by other peers"""

    if thread.peerID not in peers:
        """unknown peer"""
        peers[thread.peerID] = dict()

    """unknown peer"""
    peers[thread.peerID]["peerIP"] = request.split()[1]
    peers[thread.peerID]["peerPort"] = request.split()[2]

    answer = "PEER INFO UPDATED"
    thread.client_sock.send(answer.encode('ascii'))

def leaveGroup(thread, groups, groupsLock, groupName):
    """remove the peer from the group"""
    groupsLock.acquire()

    groups[groupName].removePeer(thread.peerID)

    groupsLock.release()

    answer = "OK - GROUP LEFT"
    thread.client_sock.send(answer.encode('ascii'))

def disconnectGroup(thread, groups, groupsLock, groupName):
    """disconnect the peer from the group (active=False)"""
    groupsLock.acquire()

    groups[groupName].disconnectPeer(thread.peerID)

    groupsLock.release()

    answer = "OK - GROUP DISCONNECTED"
    thread.client_sock.send(answer.encode('ascii'))

def peerDisconnection(thread, groups, groupsLock, peers):
    """Disconnect the peer from all the synchronization groups in which is active"""

    groupsLock.acquire()

    for group in groups.values():
        if thread.peerID in group.peersInGroup:
            if group.peersInGroup[thread.peerID].active:
                group.disconnectPeer(thread.peerID)

    groupsLock.release()

    del peers[thread.peerID]

    answer = "OK - PEER DISCONNECTED"
    thread.client_sock.send(answer.encode('ascii'))

