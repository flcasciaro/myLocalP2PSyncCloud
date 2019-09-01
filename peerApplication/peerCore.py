"""
Project: myP2PSync
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC

This code manages all the main functions of myP2PSync peers.
In detail: initializations and interactions with the tracker.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.
"""

import hashlib
import json
import os
import socket
import sys
import time
import uuid
from threading import Thread, Lock

import fileManagement
import fileSystem
import peerServer
import syncScheduler

if "networking" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import shared.networking as networking

# Obtain script path and script name, it will be useful to manage filepaths
scriptPath, scriptName = os.path.split((os.path.abspath(__file__).replace("\\", "/")))
scriptPath += "/"

# Set session files' paths
configurationFile = scriptPath + "sessionFiles/configuration.json"
previousSessionFile = scriptPath + "sessionFiles/fileList.json"

# Initialize some global variables
peerID = None
trackerAddr = None
trackerZTAddr = None
myPortNumber = None

# Lock used to avoid race conditions among threads
pathCreationLock = Lock()

# Main data structure for the groups handling.
# It's a dictionary with the following structure:
#    key: groupName
#    value: another dictionary containing group information
#           ex. status: can be ACTIVE or RESTORABLE or OTHER
#           ex. active -> number of active users in the group
#           ex. role -> role of the peer in the group

groupsList = dict()

# Data structure that keeps track of the synchronized files.
localFileTree = None


def setPeerID():
    """
    Extract from the MAC address a peerID and
    set into the associate global variable.
    :return: void
    """

    global peerID
    macAddress = uuid.getnode()
    peerID = macAddress


def trackerIsReachable():
    """
    Try to reach the tracker device: in case of success return True.
    Otherwise return False
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerAddr)
    if s is not None:
        networking.closeConnection(s, peerID)
        return True
    else:
        return False


def findTracker():
    """
    Read tracker coordinates (IP, Port) from the configuration file.
    If any problem happens reading the file (e.g. file not exists)
    return false. If the file exist and the reading operation is successfull
    return True.
    :return: boolean (True for success, False for any error)
    """

    global trackerAddr
    try:
        file = open(configurationFile, "r")
        try:
            # Configuration file wrote in JSON format
            # json.load return a dictionary
            configuration = json.load(file)

            # Extract tracker coordinates
            trackerAddr = (configuration["trackerIP"], configuration["trackerPort"])
        except ValueError:
            return False
    except FileNotFoundError:
        return False
    file.close()
    return True


def setTrackerCoordinates(coordinates):
    """
    Set tracker coordinates reading them from a string
    :param coordinates: is a string like <IPaddress>:<PortNumber>
    :return: boolean (True for success, False for failure due to a
                        bad format of the cocrdinate string)
    """

    global trackerAddr
    try:
        trackerAddr = (coordinates.split(":")[0], coordinates.split(":")[1])
        return True
    except IndexError:
        return False


def getTrackerZTAddr():
    """
    Retrives the ZeroTier IP address from the tracker
    and set the associated global variable trackerZTAddr
    :return: void
    """

    global trackerZTAddr

    s = networking.createConnection(trackerAddr)
    if s is None:
        return

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "INFO"
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    trackerZTAddr = eval(answer)


def retrieveGroups():
    """
    Retrieves groups from the tracker and update local groups list.
    In case of error return immediately without updating local groups.
    :return: boolean (True for success, False for any error)
    """
    global groupsList

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "GROUPS"
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: group not restored
        print('Received from the tracker :', answer)
        return False
    else:
        # set the local groups list equals to the retrieved one
        # split operation in order to skip the initial 'OK -'
        groupsList = eval(answer.split(" ", 2)[2])

    return True


def restoreGroup(groupName):
    """
    Restore a group by sending a request to the tracker.
    In case of success update my local groups list setting the group status to ACTIVE.
    :param groupName: is the name of the group that I want to restore
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "RESTORE {}".format(groupName)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: group not restored
        print('Received from the tracker :', answer)
        return False
    else:
        # group successfully restored: set group status to ACTIVE
        groupsList[groupName]["status"] = "ACTIVE"

        if localFileTree.getGroup(groupName) is None:
            localFileTree.addGroup(fileSystem.Node(groupName, True))

        # initialize file list for the group
        startGroupSync(groupName)

        return True


def restoreAll():
    """
    Restore all the groups with status equals to RESTORABLE.
    :return: a string containing the names of all the restored groups.
    """

    restoredGroups = ""

    for group in groupsList.values():
        if group["status"] == "RESTORABLE":
            if restoreGroup(group["name"]):
                # group successfully restored
                restoredGroups += group["name"]
                restoredGroups += ", "

    l = len(restoredGroups)
    # return the string removing last comma and space (if present)
    return restoredGroups[0:l - 2]


def joinGroup(groupName, token):
    """
    Join a group by sending a request to the tracker.
    :param groupName: is the name of the group that peer want to join
    :param token: it's the access token (password)
    :return: boolean (True for success, False for any error) (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    # encrypt the token using the md5 algorithm
    encryptedToken = hashlib.md5(token.encode())

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "JOIN {} {}".format(groupName, encryptedToken.hexdigest())
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: group not joined
        print('Received from the tracker :', answer)
        return False
    else:
        # group successfully joined: set group status to ACTIVE
        groupsList[groupName]["status"] = "ACTIVE"

        if localFileTree.getGroup(groupName) is None:
            localFileTree.addGroup(fileSystem.Node(groupName, True))

        # initialize file list for the group
        startGroupSync(groupName)

        return True


def createGroup(groupName, groupTokenRW, groupTokenRO):
    """
    Create a new group by sending a request to the tracker with all the necessary information
    :param groupName: name of the group
    :param groupTokenRW: token for Read&Write access
    :param groupTokenRO: token for ReadOnly access
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    # encrypt the two tokens using the md5 algorithm
    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                                        encryptedTokenRW.hexdigest(),
                                                                                        encryptedTokenRO.hexdigest())
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: group not created
        print('Received from the tracker :', answer)
        return False
    else:
        # group successfully created: add it to my local groups list
        groupsList[groupName] = dict()
        groupsList[groupName]["name"] = groupName
        groupsList[groupName]["status"] = "ACTIVE"
        groupsList[groupName]["total"] = 1
        groupsList[groupName]["active"] = 1
        groupsList[groupName]["role"] = "MASTER"

        localFileTree.addGroup(fileSystem.Node(groupName, True))

        return True


def changeRole(groupName, targetPeerID, action):
    """
    Change the role of a peer in a group (Master peers only)
    :param groupName: is the name of the group on which the change will be applied
    :param targetPeerID: is the peerID of the peer target of the change
    :param action: can be ADD_MASTER, CHANGE_MASTER, TO_RW, TO_RO
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: role not changed
        print('Received from the tracker :', answer)
        return False
    else:
        # tracker successfully changed role
        if action.upper() == "CHANGE_MASTER":
            # set the peer itself (former master) to RW
            groupsList[groupName]["role"] = "RW"
        return True


def retrievePeers(groupName, selectAll):
    """
    Retrieve a list containg all the peers of a group.
    If selectAll = False retrieve only ACTIVE peers
    :param groupName: name of the group
    :param selectAll: boolean (True for success, False for any error) value
    :return: list of peers
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return None

    if selectAll:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "PEERS {} {} ".format(groupName, tmp)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return None

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return None
        print('Received from the tracker :', answer)
        peersList = None
    else:
        # split operation in order to skip the initial 'OK -'
        peersList = eval(answer.split(" ", 2)[2])

    return peersList


def startPeer():
    """
    Load previous session information about files.
    Start a server thread on a free port.
    Finally send coordinates to central tracker in order to be
    reachable from other peers.
    :return: tracker object
    """

    # load local file tree with previous session information (if any)
    global localFileTree
    localFileTree = fileSystem.getFileStatus(previousSessionFile)
    if localFileTree is None:
        return None

    # create and start the scheduler thread
    schedulerThread = Thread(target=syncScheduler.scheduler, args=())
    schedulerThread.daemon = True
    schedulerThread.start()

    # join the ZeroTier virtual network
    zeroTierIP = networking.joinNetwork()

    # retrieve ZT IP address of the tracker
    getTrackerZTAddr()

    # create a server thread which will ask on all the IP addresses
    # including the ZeroTier IP address
    # port will be choose among available ones
    server = peerServer.Server()
    server.daemon = True
    server.start()

    # wait for serverStart in order to retrieve the choosen port number
    while not server.serverStart:
        pass

    # get peer server port number
    global myPortNumber
    myPortNumber = server.port

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return None

    # send my IP address and port number to tracker
    # in order to be reachable from other peers
    try:
        message = str(peerID) + " " + "HERE {} {}".format(zeroTierIP, myPortNumber)
        networking.mySend(s, message)
        __ = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return None

    return server


def startGroupSync(groupName):
    """
    Starts eventual required synchronization in a specific group.
    First of all, it retrieves files information from the tracker.
    Information retrieved are compared to local information
    belonging to a previous session of the group (if any)
    in order to detect added/removed/updated files, reacting
    properly to these events
    :param groupName: selected group
    :return: void
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return

    # retrieves file information from the tracker
    try:
        message = str(peerID) + " " + "GET_FILES {}".format(groupName)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return immediately
        print("Received from the tracker: ", answer)
        return
    else:
        # split operation in order to skip the initial 'OK -'
        updatedFileList = eval(answer.split(" ", 2)[2])

    # call the function that evaluates the information retrieved from the tracker
    # comparing them with local information about a previous session (if it exists)
    updateLocalGroupTree(groupName, localFileTree.getGroup(groupName), updatedFileList)


def updateLocalGroupTree(groupName, localGroupTree, updatedFileList):
    """
    Compare updatedFileList (retrieved from the tracker) with
    localGroupTree (previous session info) in order to find differences.
    e.g. a file in the tracker has a bigger timestamp, peer need to synchronize it
    e.g. a file in the tracker is not present locally, peer need to add it and synchronize
    e.g. a file present locally is not present anymore in the tracker, peer need to remove it
    :param groupName: name of the group that is foing to be initialized
    :param localGroupTree: fileTree of a certain group - peer side
    :param updatedFileList: fileTree (in form of list) retrieved from the tracker
    :return: void
    """

    # list used for check removed file presence
    trackerTreePaths = list()

    for fileInfo in updatedFileList:

        treePath = fileInfo["treePath"]
        trackerTreePaths.append(treePath)

        # retrieve file node in the local tree
        localNode = localGroupTree.findNode(treePath)

        if localNode is not None:
            # node found: file already added, verify if it needs a sync operation

            myFile = localNode.file

            myFile.syncLock.acquire()

            if myFile.timestamp == fileInfo["timestamp"] and myFile.status == "S":
                # file is synchronized
                if myFile.availableChunks is None:
                    # now the peer is able to upload chunks
                    myFile.initSeed()

            if myFile.timestamp == fileInfo["timestamp"] and myFile.status == "D":
                # file have been not synchronized yet e.g. partial sync
                myFile.status = "D"
                task = syncScheduler.syncTask(groupName, myFile.treePath, myFile.timestamp)
                syncScheduler.appendTask(task)

            elif myFile.timestamp < fileInfo["timestamp"]:
                # local version is not the last one
                # put file into a synchronization status
                myFile.timestamp = int(fileInfo["timestamp"])
                myFile.filesize = int(fileInfo["filesize"])
                myFile.previousChunks = list()
                myFile.status = "D"
                task = syncScheduler.syncTask(groupName, myFile.treePath, myFile.timestamp)
                syncScheduler.appendTask(task)

            myFile.syncLock.release()

        else:

            # file not found locally, add it
            path = scriptPath + "filesSync/" + groupName + '/'

            tmp, filename = os.path.split(treePath)
            filepath = path + treePath
            path += tmp

            # create the path if it doesn't exist
            pathCreationLock.acquire()
            if not os.path.exists(path):
                # print("Creating the path: " + path)
                os.makedirs(path)
            pathCreationLock.release()

            # create File object
            file = fileManagement.File(groupName=groupName, treePath=treePath,
                                       filename=filename, filepath=filepath,
                                       filesize=fileInfo["filesize"], timestamp=fileInfo["timestamp"],
                                       status="D", previousChunks=list())

            localGroupTree.addNode(treePath, file)

            # add synchronization task to the scheduler queue
            task = syncScheduler.syncTask(groupName, file.treePath, file.timestamp)
            syncScheduler.appendTask(task)

    # extract from the group file tree the list of all the file
    localTreePaths = localGroupTree.getFileTreePaths()

    # check if there are removed files:
    # file has been removed if it present in the local list
    # but it's not present in tracker updated list
    for treePath in localTreePaths:
        if treePath not in trackerTreePaths:
            localGroupTree.removeNode(treePath, True)


def addFiles(groupName, filepaths, directory):
    """
    Add a list of files to a synchronization group.
    :param groupName: name of the group in which files will be added
    :param filepaths: filepaths list of the files that will be added
    :param directory: directory path (empty if the file doesn't belong a directory)
    :return: boolean (True for success, False for any error)
    """

    # list of dictionary, where each dict contains all the info required
    # from the tracker to add a file in the group
    filesInfo = list()

    # WP stands for Without FilePath: it's a copy of filesInfo but without filepaths
    # because I don't need to send them to the tracker
    filesInfoWFP = list()

    if directory == "":
        for filepath in filepaths:
            fileInfo = dict()
            # split filepath into directoryPath and filename, saving only the latter
            __, fileInfo["treePath"] = os.path.split(filepath)
            fileInfo["filepath"] = filepath
            fileInfo["filesize"], fileInfo["timestamp"] = fileManagement.getFileStat(filepath)
            filesInfo.append(fileInfo)

            fileInfoWFP = fileInfo.copy()
            del fileInfoWFP["filepath"]
            filesInfoWFP.append(fileInfoWFP)

    else:
        # it's a directory
        for filepath in filepaths:
            fileInfo = dict()
            # remove dirPath from the filename
            # e.g.  filepath:   C://home/Desktop/file.txt
            #       directory:  C://home/Desktop
            #       dirPath:    C://home
            #       filename:   Desktop/file.txt
            dirPath, __ = os.path.split(directory)
            fileInfo["treePath"] = filepath.replace(dirPath, "")[1:]
            fileInfo["filepath"] = filepath
            fileInfo["filesize"], fileInfo["timestamp"] = fileManagement.getFileStat(filepath)
            filesInfo.append(fileInfo)

            fileInfoWFP = fileInfo.copy()
            del fileInfoWFP["filepath"]
            filesInfoWFP.append(fileInfoWFP)

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "ADDED_FILES {} {}".format(groupName, str(filesInfoWFP))
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print("Received from the tracker: ", answer)
        return False
    else:

        groupTree = localFileTree.getGroup(groupName)

        for fileInfo in filesInfo:
            # add file to the personal list of files of the peer

            filename = fileInfo["treePath"].split("/")[-1]
            treePath = fileInfo["treePath"]

            file = fileManagement.File(groupName=groupName, treePath=treePath,
                                       filename=filename, filepath=fileInfo["filepath"],
                                       filesize=fileInfo["filesize"], timestamp=fileInfo["timestamp"],
                                       status="S", previousChunks=list())

            groupTree.addNode(treePath, file)
            file.initSeed()

        # retrieve the list of active peers for the file
        activePeers = retrievePeers(groupName, selectAll=False)

        # notify other active peers
        for peer in activePeers:

            s = networking.createConnection(peer["address"])
            if s is None:
                continue

            try:
                # send request message and wait for the answer, then close the socket
                message = str(peerID) + " " + "ADDED_FILES {} {}".format(groupName, str(filesInfoWFP))
                networking.mySend(s, message)
                __ = networking.myRecv(s)
                networking.closeConnection(s, peerID)
            except (socket.timeout, RuntimeError, ValueError):
                networking.closeConnection(s, peerID)
                continue

        return True


def removeFiles(groupName, treePaths):
    """
    Remove a list of file from the synchronization group.
    :param groupName: name of the group from which files will be removed
    :param treePaths: list of treePaths of the files that will be removed
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "REMOVED_FILES {} {}".format(groupName, str(treePaths))
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print('Received from the tracker :', answer)
        return False
    else:
        # remove files from the local file list

        groupTree = localFileTree.getGroup(groupName)

        for treePath in treePaths:

            key = groupName + "_" + treePath
            if key in syncScheduler.syncThreads:
                groupTree.removeNode(treePath, False)
                syncScheduler.stopSyncThread(key, syncScheduler.FILE_REMOVED)
            else:
                groupTree.removeNode(treePath, True)

        # retrieve the list of active peers for the file
        activePeers = retrievePeers(groupName, selectAll=False)

        # notify other active peers
        for peer in activePeers:

            s = networking.createConnection(peer["address"])
            if s is None:
                continue

            try:
                # send request message and wait for the answer, then close the socket
                message = str(peerID) + " " + "REMOVED_FILES {} {}".format(groupName, str(treePaths))
                networking.mySend(s, message)
                __ = networking.myRecv(s)
                networking.closeConnection(s, peerID)
            except (socket.timeout, RuntimeError, ValueError):
                networking.closeConnection(s, peerID)
                continue

        return True


def updateFiles(groupName, files):
    """
    Update a list of file in the synchronization group,
    making them ready to be acknowledged from other peers.
    :param groupName: name of the group from which files will be updated
    :param files: list of tuples (fileObject, timestamp)
    :return: void
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    # collect information required for the update operation
    filesInfo = list()

    for f in files:
        file = f[0]
        fileInfo = dict()
        fileInfo["treePath"] = file.treePath
        fileInfo["filesize"] = file.filesize
        fileInfo["timestamp"] = file.timestamp
        filesInfo.append(fileInfo)

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "UPDATED_FILES {} {}".format(groupName, str(filesInfo))
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print('Received from the tracker :', answer)
        return False
    else:

        for f in files:
            file = f[0]
            timestamp = f[1]
            key = file.groupName + "_" + file.treePath
            # stop possible synchronization thread
            syncScheduler.stopSyncThread(key, syncScheduler.FILE_UPDATED)

            # make the peer ready to upload chunks
            if file.syncLock.acquire(blocking=False):
                # file not used by any sinchronization process
                file.status = "S"
                file.initSeed()
                file.syncLock.release()
            else:
                # file is currently in synchronization
                # create a thread which will wait under the end of the synchronization
                # and then it will update file state
                t = Thread(target=waitSyncAndUpdate, args=(file, timestamp))
                t.daemon = True
                t.start()

        # retrieve the list of active peers for the file
        activePeers = retrievePeers(groupName, selectAll=False)

        # notify other active peers
        for peer in activePeers:

            s = networking.createConnection(peer["address"])
            if s is None:
                continue

            try:
                # send request message and wait for the answer, then close the socket
                message = str(peerID) + " " + "UPDATED_FILES {} {}".format(groupName, str(filesInfo))
                networking.mySend(s, message)
                __ = networking.myRecv(s)
                networking.closeConnection(s, peerID)
            except (socket.timeout, RuntimeError, ValueError):
                networking.closeConnection(s, peerID)
                continue

        return True


def waitSyncAndUpdate(file, timestamp):
    """
    Wait until the file lock is released and then update the file object
    :param file: File object to update
    :param timestamp: timestamp of the update operation
    :return: void
    """

    # iterate until the lock is blocked
    # sleeping for 0.5 second after a False check
    while not file.syncLock.acquire(blocking=False):
        time.sleep(0.5)

    if timestamp == file.timestamp:
        # equals timestamp, operation still valid
        file.status = "S"
        file.initSeed()
    file.syncLock.release()


def leaveGroup(groupName):
    """
    Leave a group by sending a request to the tracker.
    Stop eventual running sync threads.
    :param groupName: name of the group that will be left
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "LEAVE Group: {}".format(groupName)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print('Received from the tracker :', answer)
        return False
    else:
        # stop every synchronization thread working on file of the group
        # and remove group related tasks from the queue
        syncScheduler.stopSyncThreadsByGroup(groupName, syncScheduler.SYNC_STOPPED)
        syncScheduler.removeGroupTasks(groupName)

        groupsList[groupName]["status"] = "OTHER"

        return True


def disconnectGroup(groupName):
    """
    Disconnect the peer from the group (the group becomes restorable).
    Stop eventual running sync threads.
    :param groupName: name of the group from which the peer want to disconnect
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)
    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "DISCONNECT Group: {}".format(groupName)
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print('Received from the tracker :', answer)
        return False
    else:
        # stop every synchronization thread working on file of the group
        # and remove group related tasks from the queue
        syncScheduler.stopSyncThreadsByGroup(groupName, syncScheduler.SYNC_STOPPED)
        syncScheduler.removeGroupTasks(groupName)

        groupsList[groupName]["status"] = "RESTORABLE"

        return True


def peerExit():
    """
    Disconnect peer from all the active groups by sending a request to the tracker.
    Furthermore, stop all the working synchronization thread.
    :return: boolean (True for success, False for any error)
    """

    s = networking.createConnection(trackerZTAddr)

    if s is None:
        return False

    try:
        # send request message and wait for the answer, then close the socket
        message = str(peerID) + " " + "EXIT"
        networking.mySend(s, message)
        answer = networking.myRecv(s)
        networking.closeConnection(s, peerID)
    except (socket.timeout, RuntimeError, ValueError):
        networking.closeConnection(s, peerID)
        return False

    if answer.split(" ", 1)[0] == "ERROR":
        # tracker replied with an error message: return False
        print('Received from the tracker :', answer)
        return False
    else:

        # stop scheduler
        syncScheduler.stopScheduler()
        syncScheduler.removeAllTasks()

        # stop every working synchronization thread
        syncScheduler.stopAllSyncThreads(syncScheduler.SYNC_STOPPED)

        # leave ZetoTier network
        networking.leaveNetwork()

        # wait for eventual sync threads termination
        time.sleep(3)

        # save session status
        fileSystem.saveFileStatus(localFileTree, previousSessionFile)

        return True
