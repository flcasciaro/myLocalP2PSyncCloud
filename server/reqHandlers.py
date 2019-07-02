"""
Project: myP2PSync
Code for serving clients (myP2PSync peers) requests.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""

from group import Group


def imHere(request, peers, peerID, publicAddr):
    """
    Store IP address and port number of a peer.
    These two values represents where the peer is running
    its server function, waiting for other peers messages.
    :param request: "HERE <zeroTierIP>, <PortNumber>"
    :param peers: server data structure
    :param peerID: id of the peer
    :param publicAddr: public IP address of the client
    :return: string message containing the public IP of the peer
    """
    peers[peerID] = dict()
    peers[peerID]["address"] = (request.split()[1], request.split()[2])

    answer = "OK - {}".format(publicAddr[0])
    return answer


def sendGroups(groups, peerID):
    """
    This function returns the list of active, restorable and other groups for a certain peer.
    :param groups: server data structure
    :param peerID: id of the peer
    :return: list of groups, each group is described with a dictionary
    """
    groupsList = dict()

    for g in groups.values():
        # retrieve group information
        groupsList[g.name] = g.getPublicInfo()
        # set specific peer information
        if peerID in g.peersInGroup:
            groupsList[g.name]["role"] = g.peersInGroup[peerID].role
            if g.peersInGroup[peerID].active:
                groupsList[g.name]["status"] = "ACTIVE"
            else:
                groupsList[g.name]["status"] = "RESTORABLE"
        else:
            groupsList[g.name]["role"] = ""
            groupsList[g.name]["status"] = "OTHER"

    return "OK - " + str(groupsList)


def restoreGroup(request, groups, peerID):
    """
    Makes the user active in the group specified in the message.
    :param request: "RESTORE <groupName>"
    :param groups: server data structure
    :param peerID: id of the peer
    :return: string message
    """

    groupName = request.split()[1]
    if groupName in groups:
        if peerID in groups[groupName].peersInGroup:
            if not groups[groupName].peersInGroup[peerID].active:  # if not already active
                groups[groupName].restorePeer(peerID)
                answer = "OK - GROUP {} RESTORED".format(groupName)
            else:
                answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER ALREADY ACTIVE".format(groupName)
        else:
            answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER DOESN'T BELONG TO IT".format(groupName)
    else:
        answer = "ERROR - IT'S NOT POSSIBLE TO RESTORE GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    return answer


def joinGroup(request, groups, peerID):
    """
    Makes the user active in a new group,
    choosing also the role as function of the token provided.
    :param request: "JOIN <groupName> <token>"
    :param groups: server data structure
    :param peerID: id of the peer
    :return:
    """

    groupName = request.split()[1]
    tokenProvided = request.split()[2]

    if groupName in groups:
        if tokenProvided == groups[groupName].tokenRW or tokenProvided == groups[groupName].tokenRO:
            if tokenProvided == groups[groupName].tokenRW:
                role = "RW"
                answer = "OK - GROUP {} JOINED IN ReadWrite MODE".format(groupName)
            else:
                role = "RO"
                answer = "OK - GROUP {} JOINED IN ReadOnly MODE".format(groupName)
            groups[groupName].addPeer(peerID, True, role)
        else:
            answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - WRONG TOKEN".format(groupName)
    else:
        answer = "ERROR - IMPOSSIBLE TO JOIN GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    return answer


def createGroup(request, groups, groupsLock, peerID):
    """This function allows a peer to create a new synchronization group
    specifying the groupName and the tokens. The creator peer become also the master
    of the new group."""

    newGroupName = request.split()[2]
    newGroupTokenRW = request.split()[4]
    newGroupTokenRO = request.split()[6]

    groupsLock.acquire()

    if newGroupName not in groups:
        """create the new group and insert in the group dictionary"""

        newGroup = Group(newGroupName, newGroupTokenRW, newGroupTokenRO)
        newGroup.addPeer(peerID, True, "Master")
        groups[newGroupName] = newGroup

        answer = "OK - GROUP {} SUCCESSFULLY CREATED".format(newGroupName)
    else:
        answer = "ERROR - IMPOSSIBLE TO CREATE GROUP {} - GROUP ALREADY EXIST".format(newGroupName)

    groupsLock.release()

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
            peerInfo["address"] = peers[peer]["address"]
            peerInfo["active"] = groups[groupName].peersInGroup[peer].active
            peerInfo["role"] = groups[groupName].peersInGroup[peer].role
            peersList.append(peerInfo)
        answer = "OK - " + str(peersList)
    else:
        answer = "ERROR - GROUP {} DOESN'T EXIST".format(groupName)

    return answer


def addedFiles(request, groups, groupsLock, peerID):
    try:
        requestFields = request.split(" ", 2)
        groupName = requestFields[1]
        filesInfo = eval(requestFields[2])

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGE"
                else:
                    for fileInfo in filesInfo:
                        groups[groupName].addFile(fileInfo["treePath"], fileInfo["filesize"], fileInfo["timestamp"])
                    answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer


def removedFiles(request, groups, groupsLock, peerID):
    """request is REMOVE_FILES <groupname> <filesInfo>"""

    try:
        requestFields = request.split(" ", 2)
        groupName = requestFields[1]
        treePaths = eval(requestFields[2])

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGE"
                else:
                    for tp in treePaths:
                        groups[groupName].removeFile(tp)
                    answer = "OK - FILES REMOVED FROM THE GROUP"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer


def updatedFiles(request, groups, groupsLock, peerID):
    """request is UPDATE_FILES <groupname> <filesInfo>"""

    try:
        requestFields = request.split(" ", 2)
        groupName = requestFields[1]
        filesInfo = eval(requestFields[2])

        groupsLock.acquire()

        if groupName in groups:
            if peerID in groups[groupName].peersInGroup:
                if groups[groupName].peersInGroup[peerID].role.upper() == "RO":
                    answer = "ERROR - PEER DOESN'T HAVE ENOUGH PRIVILEGES"
                else:
                    for fileInfo in filesInfo:
                        groups[groupName].updateFile(fileInfo["treePath"], fileInfo["filesize"], fileInfo["timestamp"])
                    answer = "OK - FILES SUCCESSFULLY UPDATED"
            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"
        groupsLock.release()

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer


def getFiles(request, groups, peerID):
    try:
        groupName = request.split()[1]

        if groupName in groups:
            g = groups[groupName]
            if peerID in g.peersInGroup:

                filesInfo = list()
                for file in g.filesInGroup.values():
                    fileDict = dict()
                    fileDict["treePath"] = file.filename
                    fileDict["filesize"] = file.filesize
                    fileDict["timestamp"] = file.timestamp
                    filesInfo.append(fileDict)

                answer = "OK - " + str(filesInfo)

            else:
                answer = "ERROR - PEER DOESN'T BELONG TO THE GROUP"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

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


def peerExit(groups, groupsLock, peerID):
    """Disconnect the peer from all the synchronization groups in which is active"""

    groupsLock.acquire()

    for group in groups.values():
        if peerID in group.peersInGroup:
            if group.peersInGroup[peerID].active:
                group.disconnectPeer(peerID)

    groupsLock.release()

    answer = "OK - PEER DISCONNECTED"
    return answer
