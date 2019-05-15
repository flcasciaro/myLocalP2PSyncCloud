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

configurationFile = "sessionFiles/configuration.json"
previousSessionFile = "sessionFiles/fileList.json"
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
value: filename, groupname, filepath, filesize, lastModified, status"""
localFileList = dict()

BUFSIZE = 4096


def setPeerID():
    global peerID
    """peer unique Identifier obtained from the MAC address of the machine"""
    macAddress = uuid.getnode()
    # peerID = int(time.ctime(os.path.getctime(configurationFile))) & macAddress
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
    return True


def setServerCoordinates(coordinates):
    global serverIP, serverPort
    serverIP = coordinates.split(":")[0]
    serverPort = coordinates.split(":")[1]


def createSocket(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, int(port)))
    return s


def closeSocket(sock):
    # close the connection sock
    message = "BYE"
    sock.send(message.encode('ascii'))

    data = sock.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))
    if data.decode('ascii').rstrip() == "BYE PEER":
        # time.sleep(0.1)
        sock.close()
    else:
        serverError()


def serverError():
    print("UNEXPECTED ANSWER OF THE SERVER")
    exit(-1)


def serverUnreachable():
    print("UNABLE TO REACH THE SERVER")
    exit(-1)


def handshake():
    s = createSocket(serverIP, serverPort)

    message = "I'M {}".format(peerID)
    s.send(message.encode('ascii'))

    answer = s.recv(BUFSIZE).decode('ascii').strip()

    if answer != "HELLO {}".format(peerID):
        print("Unable to perform the initial handshake with the server")
        return None

    print("Connection with server established")
    return s


def retrieveGroups():
    global activeGroupsList, restoreGroupsList, otherGroupsList

    s = handshake()

    message = "SEND ACTIVE GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(BUFSIZE)
    activeGroupsList = eval(str(data.decode('ascii')))

    message = "SEND PREVIOUS GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(BUFSIZE)
    restoreGroupsList = eval(str(data.decode('ascii')))

    message = "SEND OTHER GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(BUFSIZE)
    otherGroupsList = eval(str(data.decode('ascii')))

    closeSocket(s)


def restoreGroup(groupName, delete):
    s = handshake()

    message = "RESTORE Group: {}".format(groupName)
    # print(message)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
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
    s = handshake()

    encryptedToken = hashlib.md5(token.encode())

    message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    # print(message)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        activeGroupsList[groupName] = otherGroupsList[groupName]
        del otherGroupsList[groupName]
        return True


def createGroup(groupName, groupTokenRW, groupTokenRO):
    s = handshake()

    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)
    if str(data.decode('ascii')).split()[0] == "ERROR":
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
    s = handshake()

    print(action.upper())

    message = "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        if action.upper() == "CHANGE_MASTER":
            activeGroupsList[groupName]["role"] = "RW"
        return True


def retrievePeers(groupName, selectAll):
    s = handshake()

    if selectAll:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    message = "PEERS {} {} ".format(groupName, tmp)
    print(message)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    if data.decode('ascii').split()[0] == "ERROR":
        print('Received from the server :', str(data.decode('ascii')))
        peersList = None
    else:
        peersList = eval(str(data.decode('ascii')))

    closeSocket(s)

    # activeGroupsList[groupName]["peersList"] = peersList
    return peersList


def updateLocalFileList():
    updatedFileList = dict()

    for groupName in activeGroupsList:

        s = handshake()

        message = "GET_FILES {}".format(groupName)
        s.send(message.encode('ascii'))

        data = s.recv(BUFSIZE)
        print('Received from the server :', str(data.decode('ascii')))

        closeSocket(s)

        if str(data.decode('ascii')).split()[0] == "ERROR":
            continue
        else:
            """merge the current and the retrieved dictionaries 
            (concatenation of dictionaries of different groups)"""
            groupFileList = eval(str(data.decode('ascii')))
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
            if localFileList[key].syncLock.acquire(blocking=False):

                """try to lock the file in order to update local stats
                if it's not possible to acquire the lock (acquire return false)
                there is a synchronization process already running"""
                localFileList[key].updateFileStat()
                if localFileList[key].lastModified == file["lastModified"]:
                    localFileList[key].status = "S"
                elif localFileList[key].lastModified < file["lastModified"]:
                    localFileList[key].lastModified = file["lastModified"]
                    localFileList[key].initDownload()
                    localFileList[key].status = "D"
                elif localFileList[key].lastModified > file["lastModified"]:
                    localFileList[key].status = "U"
                localFileList[key].syncLock.release()

        else:
            """new file discovered"""
            path = "filesSync/" + file["groupName"]
            if not os.path.exists(path):
                print("creating the path: " + path)
                os.makedirs(path)
            filepath = path + "/" + file["filename"]
            localFileList[key] = fileManagement.File(groupName=file["groupName"],
                                                     filename=file["filename"],
                                                     filepath=filepath,
                                                     filesize=file["filesize"],
                                                     lastModified=file["lastModified"],
                                                     status="D")

    for file in localFileList.values():

        #Automatically update the file
        """
        if file.status == "U":
            if updateFile(file):
                file.status = "S
        """
        #Automatically sync file
        if file.status == "D":
            syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
            syncThread.start()


def updateFile(file):
    s = handshake()

    message = "UPDATE_FILE {} {} {} {}".format(file.groupName, file.filename,
                                               file.filesize, file.lastModified)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        file.iHaveIt()
        return True



def addFile(filepath, groupName):
    filePathFields = filepath.split('/')
    """select just the effective filename, discard the path"""
    filename = filePathFields[len(filePathFields) - 1]

    filesize, datetime = fileManagement.getFileStat(filepath)

    s = handshake()

    message = "ADD_FILE {} {} {} {}".format(groupName, filename, filesize, datetime)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        """add file to the personal list of files of the peer"""
        localFileList[groupName + "_" + filename] = fileManagement.File(groupName, filename,
                                                                        filepath, filesize, datetime, "S")
        return True


def removeFile(filename, groupName):
    s = handshake()

    message = "REMOVE_FILE {} {}".format(groupName, filename)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        """remove file from the personal list for the group"""
        del localFileList[groupName + "_" + filename]
        return True


def leaveGroup(groupName):
    s = handshake()

    message = "LEAVE Group: {}".format(groupName)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        otherGroupsList[groupName] = activeGroupsList[groupName]
        del activeGroupsList[groupName]
        return True


def disconnectGroup(groupName):
    s = handshake()

    message = "DISCONNECT Group: {}".format(groupName)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
        return False
    else:
        restoreGroupsList[groupName] = activeGroupsList[groupName]
        del activeGroupsList[groupName]
        return True


def disconnectPeer():
    s = handshake()

    message = "PEER DISCONNECT"
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR":
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
    portNumber = 12321

    """create a server thread that listens on the port X"""
    server = Server(myIP, portNumber)
    server.start()

    s = handshake()

    message = "HERE {} {}".format(myIP, portNumber)
    s.send(message.encode('ascii'))

    data = s.recv(BUFSIZE)
    print('Received from the server :', str(data.decode('ascii')))

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
        print("[Thr {}] SocketServerThread starting with client {}".format(self.number, self.client_addr))

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
                    read_data = self.client_sock.recv(BUFSIZE)

                    # Check if socket has been closed
                    if len(read_data) == 0:
                        print('[Thr {}] {} closed the socket.'.format(self.number, self.client_addr))
                        self.stop()
                    else:
                        # Strip newlines just for output clarity
                        message = read_data.decode('ascii').rstrip()
                        manageRequest(self, message)
            else:
                print("[Thr {}] No client is connected, SocketServer can't receive data".format(self.number))
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
        self.client_sock.send(answer.encode('ascii'))
        self.stop()


