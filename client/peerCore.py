"""Peer core code of myP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import json
import os
import select
import socket
import uuid
from threading import Thread

import fileManagement
import fileSharing
import transmission

"""Obtain script path and script name, it will be useful to manage filepaths"""
scriptPath, scriptName = os.path.split((os.path.abspath(__file__)))
scriptPath += "/"

"""Set session files' paths"""
configurationFile = scriptPath + "sessionFiles/configuration.json"
previousSessionFile = scriptPath + "sessionFiles/fileList.json"

"""Initialize some global variables"""
peerID = None
serverIP = None
serverPort = None

"""
Main data structure for the groups handling.
It's a dictionary with the following structure:
    key: groupName
    value: another dictionary containing group information
            ex. status: can be ACTIVE or RESTORABLE or OTHER
            ex. active -> number of active users in the group
            ex. role -> role of the peer in the group
"""
groupsList = dict()

"""
Data structure that keeps track of the synchronized files.
It's a dictionary with the following structure:
    key: groupName_filename in order to uniquely identify a file
    value: a File object (see fileManagement for class File)
"""
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
        file = open(configurationFile, 'r')
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
    serverIP = coordinates.split(":")[0]
    serverPort = coordinates.split(":")[1]


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

    message = str(peerID)+ " " + "BYE"
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
        message = str(peerID)+ " " + "SEND GROUPS"
        transmission.mySend(s, message)
        answer = transmission.myRecv(s)
    except (socket.timeout, RuntimeError):
        closeSocket(s)
        return False

    groupsList = eval(answer)
    closeSocket(s)

    return True


def restoreGroup(groupName):

    s = createSocket(serverIP, serverPort)
    if s is None:
        return False

    message = str(peerID)+ " " + "RESTORE Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        groupsList[groupName]["status"] = "ACTIVE"
        return True


def restoreAll():

    restoredGroups = ""

    for group in groupsList.values():
        if group["status"] == "RESTORABLE":
                    if restoreGroup(group["name"]):
                        restoredGroups += group["name"]
                        restoredGroups += ", "

    #delete last comma and space (if any)
    l = len(restoredGroups)
    return restoredGroups[0:l - 2]


def joinGroup(groupName, token):
    s = createSocket(serverIP, serverPort)

    encryptedToken = hashlib.md5(token.encode())

    message = str(peerID)+ " " + "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        groupsList[groupName]["status"] = "ACTIVE"
        return True


def createGroup(groupName, groupTokenRW, groupTokenRO):
    s = createSocket(serverIP, serverPort)

    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    message = str(peerID)+ " " + "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)
    if data.split()[0] == "ERROR":
        return False
    else:
        groupsList[groupName] = dict()
        groupsList[groupName]["name"] = groupName
        groupsList[groupName]["status"] = "ACTIVE"
        groupsList[groupName]["total"] = 1
        groupsList[groupName]["active"] = 1
        groupsList[groupName]["role"] = "MASTER"
        return True


def changeRole(groupName, targetPeerID, action):
    """this function addresses the management of the master and the management of roles by the master"""
    s = createSocket(serverIP, serverPort)

    print(action.upper())

    message = str(peerID)+ " " + "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        if action.upper() == "CHANGE_MASTER":
            groupsList[groupName]["role"] = "RW"
        return True


def retrievePeers(groupName, selectAll):
    s = createSocket(serverIP, serverPort)

    if selectAll:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    message = str(peerID)+ " " + "PEERS {} {} ".format(groupName, tmp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        peersList = None
    else:
        peersList = eval(data)

    closeSocket(s)

    return peersList


def updateLocalFileList():

    s = createSocket(serverIP, serverPort)

    message = str(peerID) + " " + "GET_FILES"
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return
    else:
        updatedFileList = eval(data)

    """delete files removed from groups (if any)"""
    delete = dict()
    for key in localFileList:
        if key not in updatedFileList:
            delete[key] = True
    for key in delete:
        del localFileList[key]

    """push updated files (if any)
    download not-sync files (if any)"""
    for key, file in updatedFileList.items():

        if key in localFileList:
            myFile = localFileList[key]
            if myFile.syncLock.acquire(blocking=False):

                """try to lock the file in order to update local stats
                if it's not possible to acquire the lock (acquire return false)
                there is a synchronization process already running"""
                myFile.updateFileStat()
                if myFile.timestamp == file["timestamp"]:
                    myFile.status = "S"
                    if myFile.availableChunks is None:
                        myFile.iHaveIt()
                elif myFile.timestamp < file["timestamp"]:
                    myFile.timestamp = file["timestamp"]
                    myFile.status = "D"
                elif myFile.timestamp > file["timestamp"]:
                    myFile.status = "U"
                myFile.syncLock.release()

        else:
            """new file discovered"""
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
                                                     status="D")

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
            if file.status == "D":
                syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
                syncThread.daemon = True
                syncThread.start()
            file.syncLock.release()


def updateFile(file):
    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "UPDATE_FILE {} {} {} {}".format(file.groupName, file.filename,
                                               file.filesize, file.timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        file.iHaveIt()
        return True


def addFile(filepath, groupName):
    filePathFields = filepath.split('/')
    """select just the effective filename, discard the path"""
    filename = filePathFields[len(filePathFields) - 1]

    filesize, timestamp = fileManagement.getFileStat(filepath)

    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "ADD_FILE {} {} {} {}".format(groupName, filename, filesize, timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        """add file to the personal list of files of the peer"""
        localFileList[groupName + "_" + filename] = fileManagement.File(groupName, filename,
                                                                        filepath, filesize,
                                                                        timestamp, "S")
        return True


def removeFile(filename, groupName):
    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "REMOVE_FILE {} {}".format(groupName, filename)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        """remove file from the personal list for the group"""
        del localFileList[groupName + "_" + filename]
        return True


def leaveGroup(groupName):
    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "LEAVE Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        groupsList[groupName]["status"] = "OTHER"
        return True


def disconnectGroup(groupName):
    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "DISCONNECT Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        groupsList[groupName]["status"] = "RESTORABLE"
        return True


def disconnectPeer():
    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "PEER DISCONNECT"
    transmission.mySend(s, message)

    data = transmission.myRecv(s)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        fileManagement.saveFileStatus(previousSessionFile, localFileList)
        return True


def startSync():

    global localFileList
    localFileList = fileManagement.getPreviousFiles(previousSessionFile)
    if localFileList is None:
        return False

    """retrieve internal IP address"""
    myIP = socket.gethostbyname(socket.gethostname())
    myPortNumber = 12321

    """create a server thread that listens on the port X"""
    server = Server(myIP, myPortNumber)
    server.daemon = True
    server.start()

    s = createSocket(serverIP, serverPort)

    message = str(peerID)+ " " + "HERE {} {}".format(myIP, myPortNumber)

    transmission.mySend(s, message)

    data = transmission.myRecv(s)

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
        self.peerID = None  # it will be set after the connection establishment (socket creation)
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
