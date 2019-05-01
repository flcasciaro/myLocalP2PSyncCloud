"""Server for the group management of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import select
import socket
from threading import Thread, Lock

import reqHandlers
from groupClass import Group

"""Main data structure for groups management
It's a dictionary where the key is the GroupName and the value is
a Group object containing information about the group e.g. tokens, peers"""
groups = dict()
groupsLock = Lock()


"""Secondary data structures for peers information.
It's a dictionary where the key is the peerID and the value is
another dictionary containing information about the peer e.g. peerIP and peerPort"""
peers = dict()
peersLock = Lock()

stop = None

groupsInfoFile = "sessionFiles/groupsInfo.txt"
groupsPeersFile = "sessionFiles/groupsPeers.txt"
groupsFilesFile = "sessionFiles/groupsFiles.txt"


def initServer():
    """Initialize server data structures
    Data structures are filled with data read from local text files if they exist"""

    previous = True
    try:
        f = open(groupsInfoFile, 'r')
        for line in f:
            groupInfo = line.split()
            groups[groupInfo[0]] = Group(groupInfo[0],groupInfo[1],groupInfo[2])
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        previous = False


    if previous:
        try:
            f = open(groupsPeersFile, 'r')
            for line in f:
                peerInfo = line.split()
                """peerID is simply the MAC address of the machine
                If this string is not present in the dictionary this is the first time I find
                this peer in the file, I need to initialize the list of groups"""
                peerID = peerInfo[0]
                if peerID not in peers:
                    peers[peerID] = dict()
                    peers[peerID]["peerIP"] = None
                    peers[peerID]["peerPort"] = None
                groups[peerInfo[1]].addPeer(peerID, False, peerInfo[2])
            f.close()
        except FileNotFoundError:
            pass

        try:
            f = open(groupsFilesFile, 'r')
            for line in f:
                fileInfo = line.split()
                groupName = fileInfo[0]
                filename = fileInfo[1]
                groups[groupName].addFile(filename, fileInfo[2],
                                          fileInfo[3], fileInfo[4])
            f.close()
        except FileNotFoundError:
            pass


def saveState():
    """Save the state of groups and peers in order to allow to restore the session in future"""
    with open(groupsInfoFile, 'w') as f:
        for group in groups.values():
            f.write(group.name+" "+
                    group.tokenRW+" "+
                    group.tokenRO+" "+
                    group.totalUsers+"\n")

    with open(groupsPeersFile, 'w') as f:
        for group in groups.values():
            for peer in group.peersInGroup.values():
                f.write(peer.peerID+" "+
                        group.name+" "+
                        peer.role+"\n")


def startServer(host, port, max_clients = 10000):

    """ Initialize the server with a host and port to listen to.
    Provide a list of functions that will be used when receiving specific data """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(max_clients)
    sock_threads = []
    counter = 0 # Will be used to give a number to each thread, can be improved (re-assigning free number)

    """ Accept an incoming connection.
    Start a new SocketServerThread that will handle the communication. """
    print('Starting socket server (host {}, port {})'.format(host, port))

    while not stop:
        sock.settimeout(1)
        try:
            client_sock, client_addr = sock.accept()
        except socket.timeout:
            client_sock = None

        if client_sock:
            client_thr = SocketServerThread(client_sock, client_addr, counter)
            counter += 1
            sock_threads.append(client_thr)
            client_thr.start()

    closeServer(host, port, sock, sock_threads)

def closeServer(host, port, sock, sock_threads):
    """ Close the client socket threads and server socket if they exists. """
    print('Closing server socket (host {}, port {})'.format(host, port))

    for thr in sock_threads:
        thr.stop()
        thr.join()

    if sock:
        sock.close()

def stopServer():
    """This function will be called in order to stop the server (example using the X on the GUI or a signal)"""
    global stop
    stop = True


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

    if message.split()[0] == "I'M":
        reqHandlers.handshake(message, self)

    elif message == "SEND ACTIVE GROUPS":
        reqHandlers.sendGroups(self, groups, action ="Active")

    elif message == "SEND PREVIOUS GROUPS":
        reqHandlers.sendGroups(self, groups, action ="Previous")

    elif message == "SEND OTHER GROUPS":
        reqHandlers.sendGroups(self, groups, action ="Other")

    elif message.split()[0] == "RESTORE":
        reqHandlers.restoreGroup(message, self, groups)
        #print(groups)

    elif message.split()[0] == "JOIN":
        reqHandlers.joinGroup(message, self, groups)
        #print(groups)

    elif message.split()[0] == "CREATE":
        reqHandlers.createGroup(message, self, groups)
        #print(groups)

    elif message.split()[0] == "ROLE":
        reqHandlers.manageRole(message, self, groups, groupsLock)
        print(groups)

    elif message.split()[0] == "PEERS":
        reqHandlers.retrievePeers(message, self, groups, peers)

    elif message.split()[0] == "HERE":
        reqHandlers.imHere(message, self, peers)
        print(peers)

    elif message.split()[0] == "LEAVE":
        reqHandlers.leaveGroup(self, groups, groupsLock, message.split()[2])

    elif message.split()[0] == "DISCONNECT":
        reqHandlers.disconnectGroup(self, groups, groupsLock, message.split()[2])

    elif message == "PEER DISCONNECT":
        reqHandlers.peerDisconnection(self, groups, groupsLock, peers)

    elif message == "BYE":
        answer = "BYE PEER"
        self.client_sock.send(answer.encode('ascii'))
        self.stop()
    else:
        answer = "WTF_U_WANT"
        self.client_sock.send(answer.encode('ascii'))

if __name__ == '__main__':
    """main function, starts the server"""

    initServer()

    stop = False
    myIP = socket.gethostbyname(socket.gethostname())
    port = 45154
    startServer(myIP,port)

    #server stopped
    saveState()