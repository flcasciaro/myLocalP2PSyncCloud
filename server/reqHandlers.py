""""This script contains function that will be invoked by the server's thread in order
to serve clients request"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

from groupClass import Group


def imHere(request, peers, peerID):

    """store IP address and Port Number on which the peer can be contacted by other peers"""

    if peerID not in peers:
        """unknown peer"""
        peers[peerID] = dict()

    """unknown peer"""
    peers[peerID]["peerIP"] = request.split()[1]
    peers[peerID]["peerPort"] = request.split()[2]

    answer = "PEER INFO UPDATED"
    return answer



def sendGroups(groups, peerID):
    """This function can retrieve the list of active, previous or other groups for a certain peerID"""
    groupsList = dict()

    for g in groups.values():
        if peerID in g.peersInGroup:
            if g.peersInGroup[peerID].active:
                role = g.peersInGroup[peerID].role
                groupsList[g.name] = g.getPublicInfo(role,"ACTIVE")
            else:
                role = g.peersInGroup[peerID].role
                groupsList[g.name] = g.getPublicInfo(role,"RESTORABLE")
        else:
            groupsList[g.name] = g.getPublicInfo("","OTHER")


    return str(groupsList)


def restoreGroup(request, groups, peerID):
    """"make the user active in one of its group (already joined)"""

    groupName = request.split()[2]
    if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if not groups[groupName].peersInGroup[peerID].active: #if not already active
                    groups[groupName].restorePeer(peerID)
                    answer = "OK - GROUP {} RESTORED".format(groupName)
                else:
                    answer = "ERROR: - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER ALREADY ACTIVE".format(groupName)
            else:
                answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER DOESN'T BELONG TO IT".format(groupName)
    else:
        answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    return answer

def joinGroup(request, groups, peerID):
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
            groups[groupName].addPeer(peerID, True, role)

        else:
            answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - WRONG TOKEN".format(groupName)
    else:
        answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    return answer

def createGroup(request, groups, peerID):
    """This function allows a peer to create a new synchronization group
    specifying the groupName and the tokens. The creator peer become also the master
    of the new group."""

    newGroupName = request.split()[2]
    newGroupTokenRW = request.split()[4]
    newGroupTokenRO = request.split()[6]

    if newGroupName not in groups:
        """create the new group and insert in the group dictionary"""

        newGroup = Group(newGroupName, newGroupTokenRW, newGroupTokenRO)
        newGroup.addPeer(peerID, True, "Master")
        groups[newGroupName] = newGroup

        answer =  "OK - GROUP {} SUCCESSFULLY CREATED".format(newGroupName)
    else:
        answer =  "ERROR - IMPOSSIBLE TO CREATE GROUP {} - GROUP ALREADY EXIST".format(newGroupName)

    return answer

def manageRole(request, groups, groupsLock, peerID):

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
        if peerID in groups[groupName].peersInGroup and modPeerID in groups[groupName].peersInGroup:
            if groups[groupName].peersInGroup[peerID].role.upper() == "MASTER":

                groupsLock.acquire()
                groups[groupName].peersInGroup[modPeerID].role = newRole

                if action.upper() == "CHANGE_MASTER":
                    groups[groupName].peersInGroup[peerID].role = "RW"

                groupsLock.release()
                answer = "OK - OPERATION ALLOWED"

            else:
                answer = "ERROR - OPERATION NOT ALLOWED"
        else:
            answer = "ERROR - OPERATION NOT ALLOWED"
    else:
        answer = "ERROR - GROUP {} DOESN'T EXIST".format(groupName)

    return answer

def retrievePeers(request, groups, peers, peerID):
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
            if peer == peerID:
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

    return answer

def addFile(request, groups, groupsLock, peerID):
    """request is ADD_FILE <groupname> <filename> <filesize> <timestamp>"""

    try:
        requestFields = request.split()
        groupName = requestFields[1]
        filename = requestFields[2]
        filesize = requestFields[3]
        timestamp = int(requestFields[4])

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGE"
                else:
                    groups[groupName].addFile(filename, filesize, timestamp)
                    answer = "OK - FILE ADDED TO THE GROUP"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer

def updateFile(request, groups, groupsLock, peerID):
    """request is UPDATE_FILE <groupname> <filename> <filesize> <timestamp>"""

    try:
        requestFields = request.split()
        groupName = requestFields[1]
        filename = requestFields[2]
        filesize = requestFields[3]
        timestamp = int(requestFields[4])

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGE"
                else:
                    groups[groupName].updateFile(filename, filesize, timestamp)
                    answer = "OK - FILE ADDED TO THE GROUP"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer

def removeFile(request, groups, groupsLock, peerID):
    """request is REMOVE_FILE <groupname> <filename>"""

    try:
        requestFields = request.split()
        groupName = requestFields[1]
        filename = requestFields[2]

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGE"
                else:
                    groups[groupName].removeFile(filename)
                    answer = "OK - FILE REMOVED FROM THE GROUP"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer

def getFiles(groups, peerID):

    fileList = dict()

    for g in groups.values():
        groupName = g.name
        if peerID in g.peersInGroup:
            if g.peersInGroup[peerID].active:
                for file in groups[groupName].filesInGroup.values():
                    fileList[groupName+"_"+file.filename]=file.getFileInfo(groupName)
    answer = str(fileList)

    return answer



def leaveGroup(groups, groupsLock, groupName, peerID):
    """remove the peer from the group"""
    groupsLock.acquire()

    groups[groupName].removePeer(peerID)

    groupsLock.release()

    answer = "OK - GROUP LEFT"
    return answer

def disconnectGroup(groups, groupsLock, groupName, peerID):
    """disconnect the peer from the group (active=False)"""
    groupsLock.acquire()

    groups[groupName].disconnectPeer(peerID)

    groupsLock.release()

    answer = "OK - GROUP DISCONNECTED"
    return answer

def peerDisconnection(groups, groupsLock, peers, peerID):
    """Disconnect the peer from all the synchronization groups in which is active"""

    groupsLock.acquire()

    for group in groups.values():
        if peerID in group.peersInGroup:
            if group.peersInGroup[peerID].active:
                group.disconnectPeer(peerID)

    groupsLock.release()

    del peers[peerID]

    answer = "OK - PEER DISCONNECTED"
    return answer

