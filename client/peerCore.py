"""Peer core code of myLocalP2PSyncCLoud"""

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

scriptPath, scriptName = os.path.split((os.path.abspath(__file__)))
scriptPath += "/"

configurationFile = scriptPath + "sessionFiles/configuration.json"
previousSessionFile = scriptPath + "sessionFiles/fileList.json"
peerID = None
serverIP = None
serverPort = None
signals = None

"""main data structures for the groups handling"""
activeGroupsList = dict()
restoreGroupsList = dict()
otherGroupsList = dict()

"""data structure that keeps track of the synchronized files
key: filename+groupName in order to uniquely identify a file
value: filename, groupname, filepath, filesize, timestamp, status"""
localFileList = dict()

BUFSIZE = 4096


def setPeerID():
    global peerID
    """peer unique Identifier obtained from the MAC address of the machine"""
    macAddress = uuid.getnode()
    peerID = macAddress


def findServer():
    global serverIP, serverPort
    try:
        file = open(configurationFile, 'r')
        try:
            configuration = json.load(file)
            serverIP = configuration["serverIP"]
            serverPort = configuration["serverPort"]
        except ValueError:
            return False
    except FileNotFoundError:
        return False
    file.close()
    return serverIsReachable()


def setServerCoordinates(coordinates):
    global serverIP, serverPort
    serverIP = coordinates.split(":")[0]
    serverPort = coordinates.split(":")[1]


def createSocket(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((host, int(port)))
    except (socket.timeout, ConnectionRefusedError):
        return None
    return s


def closeSocket(s):
    # close the connection sock
    message = "BYE"
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    #print('Received from the server :', data)
    if data.rstrip() == "BYE PEER":
        # time.sleep(0.1)
        s.close()
    else:
        return


def handshake(s):

    message = "I'M {}".format(peerID)
    transmission.mySend(s, message)

    answer = transmission.myRecv(s).strip()

    if answer != "HELLO {}".format(peerID):
        print("Unable to perform the initial handshake with the server")
        return False

    #print("Successfull handshake")

    return True

def serverIsReachable():
    s = createSocket(serverIP, serverPort)
    if s is not None:
        closeSocket(s)
        return True
    else:
        return False


def retrieveGroups():
    global activeGroupsList, restoreGroupsList, otherGroupsList

    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "SEND ACTIVE GROUPS"
    transmission.mySend(s, message)
    
    data = transmission.myRecv(s)
    activeGroupsList = eval(data)

    message = "SEND PREVIOUS GROUPS"
    transmission.mySend(s, message)
    data = transmission.myRecv(s)
    restoreGroupsList = eval(data)

    message = "SEND OTHER GROUPS"
    transmission.mySend(s, message)
    data = transmission.myRecv(s)
    otherGroupsList = eval(data)

    closeSocket(s)


def restoreGroup(groupName, delete):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "RESTORE Group: {}".format(groupName)
    # print(message)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        if delete:
            activeGroupsList[groupName] = restoreGroupsList[groupName]
            del restoreGroupsList[groupName]
        return True


def restoreAll():
    delete = dict()
    for group in restoreGroupsList.values():
        delete[group["name"]] = restoreGroup(group["name"], False)

    restoredGroups = ""
    for groupName in delete:
        if delete[groupName]:
            activeGroupsList[groupName] = restoreGroupsList[groupName]
            del restoreGroupsList[groupName]
            restoredGroups += groupName
            restoredGroups += ", "

    """delete last comma and space (if any)"""
    l = len(restoredGroups)
    return restoredGroups[0:l - 2]


def joinGroup(groupName, token):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    encryptedToken = hashlib.md5(token.encode())

    message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    # print(message)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        activeGroupsList[groupName] = otherGroupsList[groupName]
        del otherGroupsList[groupName]
        return True


def createGroup(groupName, groupTokenRW, groupTokenRO):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)
    if data.split()[0] == "ERROR":
        return False
    else:
        activeGroupsList[groupName] = dict()
        activeGroupsList[groupName]["name"] = groupName
        activeGroupsList[groupName]["total"] = 1
        activeGroupsList[groupName]["active"] = 1
        activeGroupsList[groupName]["role"] = "MASTER"
        return True


def changeRole(groupName, targetPeerID, action):
    """this function addresses the management of the master and the management of roles by the master"""
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    print(action.upper())

    message = "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        if action.upper() == "CHANGE_MASTER":
            activeGroupsList[groupName]["role"] = "RW"
        return True


def retrievePeers(groupName, selectAll):

    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return None

    if selectAll:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    message = "PEERS {} {} ".format(groupName, tmp)
    print(message)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    if data.split()[0] == "ERROR":
        print('Received from the server :', data)
        peersList = None
    else:
        peersList = eval(data)

    closeSocket(s)

    # activeGroupsList[groupName]["peersList"] = peersList
    return peersList


def updateLocalFileList():
    updatedFileList = dict()

    for groupName in activeGroupsList:

        s = createSocket(serverIP, serverPort)
        if not handshake(s):
            closeSocket(s)
            return False

        message = "GET_FILES {}".format(groupName)
        transmission.mySend(s, message)

        data = transmission.myRecv(s)
        print('Received from the server :', data)

        closeSocket(s)

        if data.split()[0] == "ERROR":
            continue
        else:
            """merge the current and the retrieved dictionaries 
            (concatenation of dictionaries of different groups)"""
            groupFileList = eval(data)
            for file in groupFileList.values():
                file["groupName"] = groupName
                updatedFileList[groupName + "_" + file["filename"]] = file

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

        #if the file is not already in sync
        if file.syncLock.acquire(blocking=False):

            #Automatically update the file
            """
            if file.status == "U":
                if updateFile(file):
                    file.status = "S"
            """
            #Automatically sync file
            if file.status == "D":
                syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
                syncThread.daemon = True
                syncThread.start()
            file.syncLock.release()


def updateFile(file):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "UPDATE_FILE {} {} {} {}".format(file.groupName, file.filename,
                                               file.filesize, file.timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

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
    if not handshake(s):
        closeSocket(s)
        return False

    message = "ADD_FILE {} {} {} {}".format(groupName, filename, filesize, timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        """add file to the personal list of files of the peer"""
        localFileList[groupName + "_" + filename] = fileManagement.File(groupName, filename,
                                                                        filepath, filesize, timestamp, "S")
        return True


def removeFile(filename, groupName):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "REMOVE_FILE {} {}".format(groupName, filename)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        """remove file from the personal list for the group"""
        del localFileList[groupName + "_" + filename]
        return True


def leaveGroup(groupName):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "LEAVE Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        otherGroupsList[groupName] = activeGroupsList[groupName]
        del activeGroupsList[groupName]
        return True


def disconnectGroup(groupName):
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "DISCONNECT Group: {}".format(groupName)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        restoreGroupsList[groupName] = activeGroupsList[groupName]
        del activeGroupsList[groupName]
        return True


def disconnectPeer():
    s = createSocket(serverIP, serverPort)
    if not handshake(s):
        closeSocket(s)
        return False

    message = "PEER DISCONNECT"
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

    closeSocket(s)

    if data.split()[0] == "ERROR":
        return False
    else:
        fileManagement.saveFileStatus(previousSessionFile, localFileList)
        return True


def startSync(sig):
    global signals
    signals = sig

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
    if not handshake(s):
        closeSocket(s)
        return False

    message = "HERE {} {}".format(myIP, myPortNumber)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the server :', data)

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


