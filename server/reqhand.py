""""This script contains function that will be invoked by the server's thread in order
to serve clients request"""

import utilities

def handshake(request, thread):
    """add or update information (IP, Port) about a peer
    no peersLock, should be thread safe because only a thread is in charge of a peer"""

    thread.peerID = request.split()[1]
    request = "HELLO {}".format(thread.peerID)
    thread.client_sock.send(request.encode('ascii'))


def sendGroups(thread, groups, action):
    """This function can retrieve the list of active, previous or other groups for a certain peerID"""
    groupsList = dict()
    action = action.upper()

    if action == "ACTIVE":
        for g in groups.values():
            if thread.peerID in g["peers"]:
                if g["peers"][thread.peerID]["active"]:
                    groupsList[g["name"]] = utilities.changeGroupInfo(g, g["peers"][thread.peerID]["role"])

    elif action == "PREVIOUS":
        for g in groups.values():
            if thread.peerID in g["peers"]:
                if not g["peers"][thread.peerID]["active"]:
                    groupsList[g["name"]]= utilities.changeGroupInfo(g, g["peers"][thread.peerID]["role"])

    elif action == "OTHER":
        for g in groups.values():
            if thread.peerID not in g["peers"]:
                groupsList[g["name"]]= utilities.changeGroupInfo(g, "")

    thread.client_sock.send(str(groupsList).encode('ascii'))


def restoreGroup(request, thread, groups):
    """"make the user active in one of its group"""

    groupName = request.split()[2]
    if groupName in groups:
            if thread.peerID in groups[groupName]["peers"]:
                if not groups[groupName]["peers"][thread.peerID]["active"]: #if not already active
                    groups[groupName]["peers"][thread.peerID]["active"] = True
                    answer = "GROUP {} RESTORED".format(groupName)
                    groups[groupName]["active"] += 1
                else:
                    answer = "IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER ALREADY ACTIVE".format(groupName)
            else:
                answer = "IT'S NOT POSSIBLE TO RESTORE GROUP {} - PEER DOESN'T BELONG TO IT".format(groupName)
    else:
        answer = "IT'S NOT POSSIBLE TO RESTORE GROUP {} - GROUP DOESN'T EXIST".format(groupName)

    thread.client_sock.send(answer.encode('ascii'))

def joinGroup(request, thread, groups):
    """"make the user active in a new group group
    choosing also the role as function of the token provided"""

    groupName = request.split()[2]
    tokenProvided = request.split()[4]

    if groupName in groups:
        if tokenProvided == groups[groupName]["tokenRW"] or tokenProvided == groups[groupName]["tokenRO"]:
            groups[groupName]["peers"][thread.peerID] = dict()
            groups[groupName]["peers"][thread.peerID]["peerID"] = thread.peerID
            groups[groupName]["peers"][thread.peerID]["active"] = True
            groups[groupName]["active"] += 1
            groups[groupName]["total"] += 1
            if tokenProvided == groups[groupName]["tokenRW"]:
                groups[groupName]["peers"][thread.peerID]["role"] = "RW"
                answer = "GROUP {} JOINED IN ReadWrite MODE".format(groupName)
            elif tokenProvided == groups[groupName]["tokenRO"]:
                groups[groupName]["peers"][thread.peerID]["role"] = "RO"
                answer = "GROUP {} JOINED IN ReadOnly MODE".format(groupName)
        else:
            answer = "IMPOSSIBLE TO JOIN GROUP {} - WRONG TOKEN".format(groupName)
    else:
        answer = "IMPOSSIBLE TO JOIN GROUP {} - GROUP DOESN'T EXIST".format(groupName)

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
        groupInfo = list()
        groupInfo.append(newGroupName)
        groupInfo.append(newGroupTokenRW)
        groupInfo.append(newGroupTokenRO)
        groupInfo.append("1")     #initial total users value
        groupInfo.append("1")     #initial active users value

        newGroup = utilities.createGroupDict(groupInfo)
        newGroup["peers"][thread.peerID] = dict()
        newGroup["peers"][thread.peerID]["peerID"] = thread.peerID
        newGroup["peers"][thread.peerID]["role"] = "Master"
        newGroup["peers"][thread.peerID]["active"] = True
        groups[newGroupName] = newGroup
        answer =  "OK: GROUP {} SUCCESSFULLY CREATED".format(newGroupName)
    else:
        answer =  "ERROR: IMPOSSIBLE TO CREATE GROUP {} - GROUP ALREADY EXIST".format(newGroupName)

    thread.client_sock.send(answer.encode('ascii'))

def manageRole(request, thread, groups, groupsLock):

    action = request.split()[1]
    modPeerID = request.split()[2]
    groupName = request.split()[4]

    if action == "CHANGE_MASTER":
        newRole = "Master"
    elif action == "ADD_MASTER":
        newRole = "Master"
    elif action == "TO_RW":
        newRole = "RW"
    elif action == "TO_RO":
        newRole = "RO"

    if groupName in groups:
        if thread.peerID in groups[groupName]["peers"] and modPeerID in groups[groupName]["peers"]:
            if groups[groupName]["peers"][thread.peerID]["role"].upper() == "MASTER":

                groupsLock.acquire()
                groups[groupName]["peers"][modPeerID]["role"] = newRole

                if action.upper() == "CHANGE_MASTER":
                    groups[groupName]["peers"][thread.peerID]["role"] = "RW"

                groupsLock.release()
                answer = "OPERATION ALLOWED"

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
        for peer in groups[groupName]["peers"]:
            if not groups[groupName]["peers"][peer]["active"] and not selectAll:
                continue
            peersList.append(peers[peer])
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

def peerDisconnection(thread, groups, peers):
    """Disconnect the peer from all the synchronization groups setting the active value to False"""

    for group in groups.values():
        if thread.peerID in group["peers"]:
            group["peers"][thread.peerID]["active"] = False
            group["active"] -= 1

    del peers[thread.peerID]

