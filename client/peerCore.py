"""Peer core code of myP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import json
import os
import socket
import time
import uuid
from threading import Thread, Lock

import fileManagement
import fileSharing
import peerServer
import transmission

# Obtain script path and script name, it will be useful to manage filepaths
scriptPath, scriptName = os.path.split((os.path.abspath(__file__)))
scriptPath += "/"

# Set session files' paths
configurationFile = scriptPath + "sessionFiles/configuration.json"
previousSessionFile = scriptPath + "sessionFiles/fileList.json"

# Initialize some global variables
peerID = None
serverIP = None
serverPort = None

# Data structure that keep tracks of synchronization threads
# key : groupName_filename
# values: dict()    ->      groupName
#                           stop
syncThreads = dict()
syncThreadsLock = Lock()
MAX_SYNC_THREAD = 5

# Main data structure for the groups handling.
# It's a dictionary with the following structure:
#    key: groupName
#    value: another dictionary containing group information
#           ex. status: can be ACTIVE or RESTORABLE or OTHER
#           ex. active -> number of active users in the group
#           ex. role -> role of the peer in the group

groupsList = dict()

# Data structure that keeps track of the synchronized files.
# It's a dictionary with the following structure:
#    key: groupName_filename in order to uniquely identify a file
#    value: a File object (see fileManagement for class File)

localFileList = dict()


def setPeerID():
    """
    Extract from the MAC address a peerID and
    set into the associate global variable.
    :return: void
    """

    global peerID
    macAddress = uuid.getnode()
    peerID = macAddress


def serverIsReachable():
    """
    Try to reach the server: in case of success return True.
    Otherwise return False
    :return: boolean
    """

    s = createSocket(serverIP, serverPort)
    if s is not None:
        closeSocket(s)
        return True
    else:
        return False


def findServer():
    """
    Read server coordinates (IP, Port) from the configuration file.
    If any problem happens reading the file (e.g. file not exists)
    return false. If the file exist and the reading operation is successfull
    return serverIsReachable() value (this function try to reach the server
    and return True/False whether the server is reachable or not).
    :return: boolean
    """

    global serverIP, serverPort
    try:
        file = open(configurationFile, "r")
        try:
            # Configuration file wrote in JSON format
            # json.load return a dictionary
            configuration = json.load(file)

            # Extract server coordinates
            serverIP = configuration["serverIP"]
            serverPort = configuration["serverPort"]
        except ValueError:
            return False
    except FileNotFoundError:
        return False
    file.close()
    return serverIsReachable()


def setServerCoordinates(coordinates):
    """
    Set server coordinates reading them from a string
    :param coordinates: is a string like <IPaddress>:<PortNumber>
    :return: void
    """

    global serverIP, serverPort
    try:
        serverIP = coordinates.split(":")[0]
        serverPort = coordinates.split(":")[1]
        return True
    except IndexError:
        return False


def createSocket(ipAddress, port):
    """
    Create a socket connection with a remote host.
    In case of success return the established socket.
    In case of failure (timeout or connection refused) return None.
    :param ipAddress: IP address of the host
    :param port: port number on which the host is listening
    :return: socket or None
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((ipAddress, int(port)))
    except (socket.timeout, ConnectionRefusedError):
        return None
    return s


def closeSocket(s):
    """
    Wrapper function for socket.close().
    Coordinates the socket close operation with the server.
    Send a BYE message and wait for a reply.
    Finally close the socket anyway.
    :param s: socket which will be closed
    :return: void
    """

    message = str(peerID) + " " + "BYE"
    try:
        transmission.mySend(s, message)
        # get the answer into an "ignore" variable
        __ = transmission.myRecv(s)
    except (socket.timeout, RuntimeError):
        pass

    # close the socket anyway
    s.close()


def retrieveGroups():
    """
    Retrieves groups from the server and update local groups list.
    In case of error return immediately without updating local groups.
    :return: boolean
    """
    global groupsList

    s = createSocket(serverIP, serverPort)
    if s is None:
        return

    try:
        message = str(peerID) + " " + "SEND GROUPS"
        transmission.mySend(s, message)
        answer = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    # set the local groups list equals to the retrieved one
    groupsList = eval(answer)

    return True


def restoreGroup(groupName):
    """
    Restore a group by sending a request to the server.
    In case of success update my local groups list setting the group status to ACTIVE.
    :param groupName: is the name of the group that I want to restore
    :return: boolean
    """

    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    try:
        message = str(peerID) + " " + "RESTORE Group: {}".format(groupName)
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if data.split()[0] == "ERROR":
        # server replied with an error message: group not restored
        print('Received from the server :', data)
        return False
    else:
        # group successfully restored: set group status to ACTIVE
        groupsList[groupName]["status"] = "ACTIVE"
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
    Join a group by sending a request to the server.
    :param groupName: is the name of the group that I want to join
    :param token: is the access token (password)
    :return: boolean
    """

    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    # encrypt the token using the md5 algorithm
    encryptedToken = hashlib.md5(token.encode())

    try:
        message = str(peerID) + " " + "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if data.split()[0] == "ERROR":
        # server replied with an error message: group not joined
        print('Received from the server :', data)
        return False
    else:
        # group successfully joined: set group status to ACTIVE
        groupsList[groupName]["status"] = "ACTIVE"
        return True


def createGroup(groupName, groupTokenRW, groupTokenRO):
    """
    Create a new group by sending a request to the server with all the necessary information
    :param groupName: name of the group
    :param groupTokenRW: token for Read&Write access
    :param groupTokenRO: token for ReadOnly access
    :return: boolean
    """

    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    # encrypt the two tokens using the md5 algorithm
    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    try:
        message = str(peerID) + " " + "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                                        encryptedTokenRW.hexdigest(),
                                                                                        encryptedTokenRO.hexdigest())
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if data.split()[0] == "ERROR":
        # server replied with an error message: group not created
        print('Received from the server :', data)
        return False
    else:
        # group successfully created: add it to my local groups list
        groupsList[groupName] = dict()
        groupsList[groupName]["name"] = groupName
        groupsList[groupName]["status"] = "ACTIVE"
        groupsList[groupName]["total"] = 1
        groupsList[groupName]["active"] = 1
        groupsList[groupName]["role"] = "MASTER"
        return True


def changeRole(groupName, targetPeerID, action):
    """
    Change the role of a peer in a group (Master peers only)
    :param groupName: is the name of the group on which the change will be applied
    :param targetPeerID: is the peerID of the peer target of the change
    :param action: can be ADD_MASTER, CHANGE_MASTER, TO_RW, TO_RO
    :return: boolean
    """
    s = createSocket(serverIP, serverPort)
    if s is None:
        return False
    try:
        message = str(peerID) + " " + "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if data.split()[0] == "ERROR":
        # server replied with an error message: role not changed
        print('Received from the server :', data)
        return False
    else:
        # server successfully changed role
        if action.upper() == "CHANGE_MASTER":
            # set the peer itself (former master) to RW
            groupsList[groupName]["role"] = "RW"
        return True


def retrievePeers(groupName, selectAll):
    """
    Retrieve a list containg all the peers of a group.
    If selectAll = False retrieve only ACTIVE peers
    :param groupName: name of the group
    :param selectAll: boolean value
    :return: list of peers
    """

    s = createSocket(serverIP, serverPort)
    if s is None:
        return None

    if selectAll:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    try:
        message = str(peerID) + " " + "PEERS {} {} ".format(groupName, tmp)
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return None

    if data.split()[0] == "ERROR":
        # server replied with an error message: return None
        print('Received from the server :', data)
        peersList = None
    else:
        peersList = eval(data)

    return peersList


def updateLocalFileList():
    """
    Retrieve from the server the file list of all the active groups.
    Delete from the local list removed file (if any).
    For each file: compare local version with the server one,
                    start synchronization thread for not updated files.
    :return: void
    """

    s = createSocket(serverIP, serverPort)
    if s is None:
        return

    try:
        message = str(peerID) + " " + "GET_FILES"
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return

    if data.split()[0] == "ERROR":
        return
    else:
        updatedFileList = eval(data)

    # delete files removed from active groups (if any)
    delete = dict()
    for key in localFileList:
        groupName = key.split("_")[0]
        if groupsList[groupName]["status"] != "ACTIVE":
            continue
        if key not in updatedFileList:
            delete[key] = True
    for key in delete:
        del localFileList[key]

    # compare local timestamp with server timestamp and mark file status
    # as D (need to be synchronized), S (already synchronized) or
    # U (peer must push its version to the server)
    for key, file in updatedFileList.items():

        if key in localFileList:
            myFile = localFileList[key]
            if myFile.syncLock.acquire(blocking=False):
                # try to lock the file in order to update local stats
                # if it's not possible to acquire the lock (acquire return false)
                # there is a synchronization process already running
                if myFile.status != "D":
                    # check if local version is still the last one
                    myFile.updateFileStat()

                    if myFile.timestamp == file["timestamp"]:
                        myFile.status = "S"
                        if myFile.availableChunks is None:
                            # now the peer is able to upload chunks
                            myFile.iHaveIt()

                    elif myFile.timestamp < file["timestamp"]:
                        myFile.timestamp = file["timestamp"]
                        myFile.filesize = file["filesize"]
                        myFile.previousChunks = list()
                        myFile.status = "D"

                    elif myFile.timestamp > file["timestamp"]:
                        myFile.status = "U"

                myFile.syncLock.release()

        else:
            # new file discovered: add it to my local list
            path = scriptPath + "filesSync/" + file["groupName"]
            if not os.path.exists(path):
                print("creating the path: " + path)
                os.makedirs(path)
            filepath = path + "/" + file["filename"]
            localFileList[key] = fileManagement.File(groupName=file["groupName"],
                                                     filename=file["filename"],
                                                     filepath=filepath,
                                                     filesize=file["filesize"],
                                                     timestamp=file["timestamp"],
                                                     status="D",
                                                     previousChunks=list())

    for file in localFileList.values():

        if groupsList[file.groupName]["status"] != "ACTIVE":
            continue

        # if the file is not already in sync
        if file.syncLock.acquire(blocking=False):

            # Automatically sync file
            syncThreadsLock.acquire()
            if file.status == "D" and len(syncThreads) < MAX_SYNC_THREAD:
                # start a new synchronization thread if there are less
                # than MAX_SYNC_THREAD already active threads
                syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
                syncThread.daemon = True
                key = file.groupName + "_" + file.filename
                syncThreads[key] = dict()
                syncThreads[key]["groupName"] = file.groupName
                syncThreads[key]["stop"] = False
                syncThread.start()
            syncThreadsLock.release()
            file.syncLock.release()


def updateFile(file):
    """
    Update the version file in the server.
    :param file: file object that have to be updated into the server
    :return: boolean
    """
    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    try:
        message = str(peerID) + " " + "UPDATE_FILE {} {} {} {}".format(file.groupName, file.filename,
                                                                   file.filesize, file.timestamp)
        transmission.mySend(s, message)
        answer = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if answer.split()[0] == "ERROR":
        # server replied with an error message: return False
        print('Received from the server :', answer)
        return False
    else:
        # make the peer ready to upload chunks
        file.iHaveIt()
        return True


def addFile(filepath, groupName):
    """


    :param filepath:
    :param groupName:
    :return:
    """

    filePathFields = filepath.split('/')
    """select just the effective filename, discard the path"""
    filename = filePathFields[len(filePathFields) - 1]

    filesize, timestamp = fileManagement.getFileStat(filepath)

    s = createSocket(serverIP, serverPort)

    if s is None:
        return False

    message = str(peerID) + " " + "ADD_FILE {} {} {} {}".format(groupName, filename, filesize, timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        """add file to the personal list of files of the peer"""
        localFileList[groupName + "_" + filename] = fileManagement.File(groupName, filename,
                                                                        filepath, filesize,
                                                                        timestamp, "S", list())
        localFileList[groupName + "_" + filename].iHaveIt()
        return True


def addDir(filepaths, groupName, dirName):
    """


    :param filepaths:
    :param groupName:
    :param dirName:
    :return:
    """
    path1, __ = os.path.split(dirName)

    s = createSocket(serverIP, serverPort)
    if s is None:
        return

    for filepath in filepaths:
        filename = filepath.replace(path1, "")[1:]

        filesize, timestamp = fileManagement.getFileStat(filepath)

        message = str(peerID) + " " + "ADD_FILE {} {} {} {}".format(groupName, filename, filesize, timestamp)
        transmission.mySend(s, message)

        data = transmission.myRecv(s)

        if data.split()[0] == "ERROR":
            break
        else:
            """add file to the personal list of files of the peer"""
            localFileList[groupName + "_" + filename] = fileManagement.File(groupName, filename,
                                                                            filepath, filesize,
                                                                            timestamp, "S", list())
            localFileList[groupName + "_" + filename].iHaveIt()

    closeSocket(s)


def removeFile(filename, groupName):
    """

    :param filename:
    :param groupName:
    :return:
    """
    s = createSocket(serverIP, serverPort)

    if s is None:
        return False

    message = str(peerID) + " " + "REMOVE_FILE {} {}".format(groupName, filename)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        return False
    else:
        """remove file from the personal list for the group"""
        key = groupName + "_" + filename
        del localFileList[key]

        if key in syncThreads:
            syncThreadsLock.acquire()
            syncThreads[key]["stop"] = True
            syncThreadsLock.release()

        return True


def leaveGroup(groupName):
    """


    :param groupName:
    :return:
    """
    s = createSocket(serverIP, serverPort)

    if s is None:
        return False

    message = str(peerID) + " " + "LEAVE Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        return False
    else:
        syncThreadsLock.acquire()
        for thread in syncThreads.values():
            if thread["groupName"] == groupName:
                thread["stop"] = True
        syncThreadsLock.release()
        groupsList[groupName]["status"] = "OTHER"
        return True


def disconnectGroup(groupName):
    s = createSocket(serverIP, serverPort)

    if s is None:
        return False

    message = str(peerID) + " " + "DISCONNECT Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        return False
    else:
        syncThreadsLock.acquire()
        for thread in syncThreads.values():
            if thread["groupName"] == groupName:
                thread["stop"] = True
        syncThreadsLock.release()
        return True


def disconnectPeer():
    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    message = str(peerID) + " " + "PEER DISCONNECT"
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        return False
    else:
        syncThreadsLock.acquire()
        for thread in syncThreads.values():
            thread["stop"] = True
        syncThreadsLock.release()
        time.sleep(3)
        fileManagement.saveFileStatus(previousSessionFile, localFileList)
        return True


def startSync():
    global localFileList
    localFileList = fileManagement.getPreviousFiles(previousSessionFile)
    if localFileList is None:
        return None

    # retrieve internal IP address
    myIP = socket.gethostbyname(socket.gethostname())
    myPortNumber = 12321

    # create a server thread that listens on the port 12321
    server = peerServer.Server(myIP, myPortNumber)
    server.daemon = True
    server.start()

    s = createSocket(serverIP, serverPort)
    if s is None:
        return None

    message = str(peerID) + " " + "HERE {} {}".format(myIP, myPortNumber)

    transmission.mySend(s, message)

    # get reply into an "ignore" variable
    __ = transmission.myRecv(s)

    closeSocket(s)

    return server
