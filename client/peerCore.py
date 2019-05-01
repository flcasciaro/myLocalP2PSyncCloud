"""Peer core code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import select
import socket
import time
import uuid
from threading import Thread


configurationFile = "conf.txt"
peerID = None
serverIP = None
serverPort = None
signals = None

"""main data structures for the groups handling"""
activeGroupsList = {}
restoreGroupsList = {}
otherGroupsList = {}

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
        configuration = file.readline().split()
        serverIP = configuration[0]
        serverPort = int(configuration[1])
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
    s.connect((host, port))
    return s

def closeSocket(sock):
    # close the connection sock
    message = "BYE"
    sock.send(message.encode('ascii'))

    data = sock.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))
    if data.decode('ascii').rstrip() == "BYE PEER":
        time.sleep(0.1)
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

    answer = s.recv(1024).decode('ascii').strip()

    if answer != "HELLO {}".format(peerID):
        print ("Unable to perform the initial handshake with the server")
        return None

    print("Connection with server established")
    return s


def retrieveGroups():

    global activeGroupsList, restoreGroupsList, otherGroupsList

    s = handshake()

    message = "SEND ACTIVE GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(1024)
    activeGroupsList = eval(str(data.decode('ascii')))

    message = "SEND PREVIOUS GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(1024)
    restoreGroupsList = eval(str(data.decode('ascii')))

    message = "SEND OTHER GROUPS"
    s.send(message.encode('ascii'))
    data = s.recv(1024)
    otherGroupsList = eval(str(data.decode('ascii')))

    closeSocket(s)

def restoreGroup(groupName):

    s = handshake()

    message = "RESTORE Group: {}".format(groupName)
    print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


def restoreAll():

    for group in restoreGroupsList.values():
        restoreGroup(group["name"])




def joinGroup(groupName, token):

    s = handshake()

    encryptedToken = hashlib.md5(token.encode())

    message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    # print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


def createGroup(groupName, groupTokenRW, groupTokenRO):

    s = handshake()

    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)
    if str(data.decode('ascii')).split()[0] == "ERROR:":
        return False
    else:
        return True


def changeRole(groupName, targetPeerID, action):
    """this function addresses the management of the master and the management of roles by the master"""
    s = handshake()

    print(action.upper())

    message = "ROLE {} {} GROUP {}".format(action.upper(), targetPeerID, groupName)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR:":
        return False
    else:
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

    data = s.recv(1024)
    if data.decode('ascii').split()[0] == "ERROR":
        print('Received from the server :', str(data.decode('ascii')))
        peersList = None
        success = False
    else:
        peersList = eval(str(data.decode('ascii')))
        success = True

    closeSocket(s)

    activeGroupsList[groupName]["peersList"] = peersList
    return success

def disconnectPeer():

    s = handshake()

    message = "PEER DISCONNECT"
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

def leaveGroup(groupName):

    s = handshake()

    message = "LEAVE Group: {}".format(groupName)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR:":
        return False
    else:
        return True

def disconnectGroup(groupName):
    s = handshake()

    message = "DISCONNECT Group: {}".format(groupName)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

    if str(data.decode('ascii')).split()[0] == "ERROR:":
        return False
    else:
        return True



def startSync(sig):

    global signals
    signals = sig

    """retrieve internal IP address"""
    myIP = socket.gethostbyname(socket.gethostname())
    portNumber = 12321

    """create a server thread that listens on the port X"""
    server = Server(myIP, portNumber)
    server.start()

    s = handshake()

    message = "HERE {} {}".format(myIP, portNumber)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


class Server(Thread):
    def __init__(self, host, port, max_clients = 10):
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
        self.counter = 0 # Will be used to give a number to each thread, can be improved (re-assigning free number)
        self.__stop = False

    def run(self):
        """ Accept an incoming connection.
        Start a new SocketServerThread that will handle the communication. """
        print('Starting socket server (host {}, port {})'.format(self.host,self.port))

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
        self.peerID = None  #it will be set after the connection establishment (socket creation)
        self.__stop = False

    def run(self):
        print("[Thr {}] SocketServerThread starting with client {}".format(self.number, self.client_addr))

        while not self.__stop:
            if self.client_sock:
                # Check if the client is still connected and if data is available:
                try:
                    rdy_read, rdy_write, sock_err = select.select([self.client_sock, ], [self.client_sock, ], [], 5)
                except select.error:
                    print('[Thr {}] Select() failed on socket with {}'.format(self.number,self.client_addr))
                    self.stop()
                    return

                if len(rdy_read) > 0:
                    read_data = self.client_sock.recv(1024)

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

    if message == "EHI":
        signals.refreshEmit("ueeeeeeeeeeeeee")
        answer = "OK"
        self.client_sock.send(answer.encode('ascii'))
    elif message == "BYE":
        answer = "BYE PEER"
        self.client_sock.send(answer.encode('ascii'))
        self.stop()
