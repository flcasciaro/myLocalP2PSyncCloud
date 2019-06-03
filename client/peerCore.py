"""Peer core code of myP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import json
import os
import select
import socket
import time
import uuid
from threading import Thread, Lock

import fileManagement
import fileSharing
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

    # delete files removed from groups (if any)
    delete = dict()
    for key in localFileList:
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

                    print(myFile.timestamp)
                    print(type(myFile.timestamp))
                    print(file["filestamp"])
                    print(type(file["filestamp"]))

                    if myFile.timestamp == file["timestamp"]:
                        myFile.status = "S"
                        if myFile.availableChunks is None:
                            # now the peer is able to upload chunks
                            myFile.iHaveIt()
                    elif myFile.timestamp < file["timestamp"]:
                        myFile.timestamp = file["timestamp"]
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

        # if the file is not already in sync
        if file.syncLock.acquire(blocking=False):

            # Automatically update the file
            """
            if file.status == "U":
                if updateFile(file):
                    file.status = "S"
            """
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
        data = transmission.myRecv(s)
        closeSocket(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    if data.split()[0] == "ERROR":
        return False
    else:
        # make the peer ready to upload chunks
        file.iHaveIt()
        return True


def addFile(filepath, groupName):
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
        return True


def addDir(filepaths, groupName, dirName):
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

    closeSocket(s)


def removeFile(filename, groupName):
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
        return False

    # retrieve internal IP address
    myIP = socket.gethostbyname(socket.gethostname())
    myPortNumber = 12321

    """create a server thread that listens on the port X"""
    server = Server(myIP, myPortNumber)
    server.daemon = True
    server.start()

    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    message = str(peerID) + " " + "HERE {} {}".format(myIP, myPortNumber)

    transmission.mySend(s, message)

    # get reply into an "ignore" variable
    __ = transmission.myRecv(s)

    closeSocket(s)

    return True


class Server(Thread):
    def __init__(self, host, port, max_clients=5):
        Thread.__init__(self)
        """ Initialize the server with a host and port to listen to.
        Provide a list of functions that will be used when receiving specific data """
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(max_clients)
        self.sock_threads = []
        self.counter = 0  # Will be used to give a number to each thread, can be improved (re-assigning free number)
        self.__stop = False

    def run(self):
        """ Accept an incoming connection.
        Start a new SocketServerThread that will handle the communication. """
        print('Starting socket server (host {}, port {})'.format(self.host, self.port))

        while not self.__stop:
            self.sock.settimeout(1)
            try:
                client_sock, client_addr = self.sock.accept()
            except socket.timeout:
                client_sock = None

            if client_sock:
                client_thr = SocketServerThread(client_sock, client_addr, self.counter)
                self.counter += 1
                self.sock_threads.append(client_thr)
                client_thr.daemon = True
                client_thr.start()

        self.closeServer()

    def closeServer(self):
        """ Close the client socket threads and server socket if they exists. """
        print('Closing server socket (host {}, port {})'.format(self.host, self.port))

        for thr in self.sock_threads:
            thr.stop()
            thr.join()

        if self.sock:
            self.sock.close()

    def stopServer(self):
        """This function will be called in order to stop the server (example using the X on the GUI or a signal)"""
        self.__stop = True


class SocketServerThread(Thread):
    def __init__(self, client_sock, client_addr, number):
        """ Initialize the Thread with a client socket and address """
        Thread.__init__(self)
        self.client_sock = client_sock
        self.client_addr = client_addr
        self.number = number
        self.__stop = False

    def run(self):
        print("[Thr {}] SocketServerThread starting with peer {}".format(self.number, self.client_addr))

        while not self.__stop:
            if self.client_sock:
                # Check if the client is still connected and if data is available:
                try:
                    rdy_read, rdy_write, sock_err = select.select([self.client_sock, ], [self.client_sock, ], [], 5)
                except select.error:
                    print('[Thr {}] Select() failed on socket with {}'.format(self.number, self.client_addr))
                    self.stop()
                    return

                if len(rdy_read) > 0:
                    read_data = transmission.myRecv(self.client_sock)

                    # Check if socket has been closed
                    if len(read_data) == 0:
                        print('[Thr {}] {} closed the socket.'.format(self.number, self.client_addr))
                        self.stop()
                    else:
                        # Strip newlines just for output clarity
                        message = read_data.rstrip()
                        manageRequest(self, message)
            else:
                print("[Thr {}] No peer is connected, SocketServer can't receive data".format(self.number))
                self.stop()
        self.close()

    def stop(self):
        self.__stop = True

    def close(self):
        """ Close connection with the client socket. """
        if self.client_sock:
            print('[Thr {}] Closing connection with {}'.format(self.number, self.client_addr))
            self.client_sock.close()


def manageRequest(self, message):
    """Serves the client request"""
    print('[Thr {}] Received {}'.format(self.number, message))

    if message.split()[0] == "CHUNKS_LIST":
        fileSharing.sendChunksList(message, self, localFileList)

    if message.split()[0] == "CHUNK":
        fileSharing.sendChunk(message, self, localFileList)

    elif message == "BYE":
        answer = "BYE PEER"
        transmission.mySend(self.client_sock, answer)
        self.stop()
