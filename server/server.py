"""Server for the group management of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import json
import os
import select
import socket
from threading import Thread, Lock

import reqHandlers
import transmission
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

scriptPath, scriptName = os.path.strip((os.path.abspath(__file__)))
scriptPath += "/"

groupsInfoFile = scriptPath + 'sessionFiles/groupsInfo.json'
groupsPeersFile = scriptPath + 'sessionFiles/groupsPeers.json'
groupsFilesFile = scriptPath + 'sessionFiles/groupsFiles.json'

def initServer():
    """Initialize server data structures
    Data structures are filled with data read from local text files if they exist"""

    global groups, peers

    previous = True
    try:
        f = open(groupsInfoFile, 'r')
        try:
            groupsJson = json.load(f)
            for group in groupsJson:
                groupName = group["groupName"]
                tokenRW = group["tokenRW"]
                tokenRO = group["tokenRO"]
                groups[groupName] = Group(groupName, tokenRW, tokenRO)
            del groupsJson
        except ValueError:
            return None
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        previous = False

    if previous:
        try:
            f = open(groupsPeersFile, 'r')
            try:
                peersJson = json.load(f)
                for peer in peersJson:
                    peerID = peer["peerID"]
                    groupName = peer["groupName"]
                    role = peer["role"]
                    if peerID not in peers:
                        peers[peerID] = dict()
                        peers[peerID]["peerIP"] = None
                        peers[peerID]["peerPort"] = None
                    groups[groupName].addPeer(peerID, False, role)
                del peersJson
            except ValueError:
                return None
            f.close()
        except FileNotFoundError:
            pass

        try:
            f = open(groupsFilesFile, 'r')
            try:
                filesJson = json.load(f)
                for file in filesJson:
                    groupName = file["groupName"]
                    filename = file["filename"]
                    filesize = file["filesize"]
                    lastModified = file["lastModified"]
                    groups[groupName].addFile(filename, filesize, lastModified)
                del filesJson
            except ValueError:
                return None
            f.close()
        except FileNotFoundError:
            pass


def saveState():
    """Save the state of groups and peers in order to allow to restore the session in future"""
    groupsJson = list()
    with open(groupsInfoFile, 'w') as f:
        for group in groups.values():
            groupInfo = dict()
            groupInfo["groupName"] = group.name
            groupInfo["tokenRW"] = group.tokenRW
            groupInfo["tokenRO"] = group.tokenRO
            groupsJson.append(groupInfo)
        json.dump(groupsJson, f, indent=4)
        del groupsJson

    peersJson = list()
    with open(groupsPeersFile, 'w') as f:
        for group in groups.values():
            for peer in group.peersInGroup.values():
                peerInfo = dict()
                peerInfo["peerID"] = peer.peerID
                peerInfo["groupName"] = group.name
                peerInfo["role"] = peer.role
                peersJson.append(peerInfo)
        json.dump(peersJson, f, indent=4)
        del peersJson

    filesJson = list()
    with open(groupsFilesFile, 'w') as f:
        for group in groups.values():
            for file in group.filesInGroup.values():
                fileInfo = dict()
                fileInfo["groupName"] = group.name
                fileInfo["filename"] = file.filename
                fileInfo["filesize"] = file.filesize
                fileInfo["lastModified"] = file.filesize
                filesJson.append(fileInfo)
        json.dump(filesJson, f, indent=4)
        del filesJson


class Server:

    def __init__(self, host, port, max_clients = 5):

        """ Initialize the server with a host and port to listen to.
        Provide a list of functions that will be used when receiving specific data """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(max_clients)
        self.sock_threads = []
        self.counter = 0 # Will be used to give a number to each thread, can be improved (re-assigning free number)
        self.__stop = False

        """ Accept an incoming connection.
        Start a new SocketServerThread that will handle the communication. """
        print('Starting socket server (host {}, port {})'.format(host, port))

        while not self.__stop:
            try:
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
            except KeyboardInterrupt:
                self.stopServer()

        self.closeServer(host, port)

    def closeServer(self, host, port):
        """ Close the client socket threads and server socket if they exists. """
        print('Closing server socket (host {}, port {})'.format(host, port))

        for thr in self.sock_threads:
            thr.stop()
            thr.join()

        if self.sock:
            self.sock.close()

        print("Saving the state of the server")
        saveState()
        exit()

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

    """Serves the different client requests"""
    print('[Thr {}] Received {}'.format(self.number, message))

    if message.split()[0] == "I'M":
        reqHandlers.handshake(message, self)

    elif message.split()[0] == "SEND":
        action = message.split()[1]       #ACTIVE or PREVIOUS or OTHER
        reqHandlers.sendGroups(self, groups, action)

    elif message.split()[0] == "RESTORE":
        reqHandlers.restoreGroup(message, self, groups)

    elif message.split()[0] == "JOIN":
        reqHandlers.joinGroup(message, self, groups)

    elif message.split()[0] == "CREATE":
        reqHandlers.createGroup(message, self, groups)

    elif message.split()[0] == "ROLE":
        reqHandlers.manageRole(message, self, groups, groupsLock)

    elif message.split()[0] == "PEERS":
        reqHandlers.retrievePeers(message, self, groups, peers)

    elif message.split()[0] == "ADD_FILE":
        reqHandlers.addFile(message, self, groups, groupsLock)

    elif message.split()[0] == "UPDATE_FILE":
        reqHandlers.updateFile(message, self, groups, groupsLock)

    elif message.split()[0] == "REMOVE_FILE":
        reqHandlers.removeFile(message, self, groups, groupsLock)

    elif message.split()[0] == "GET_FILES":
        reqHandlers.getFiles(message, self, groups)

    elif message.split()[0] == "HERE":
        reqHandlers.imHere(message, self, peers)

    elif message.split()[0] == "LEAVE":
        reqHandlers.leaveGroup(self, groups, groupsLock, message.split()[2])

    elif message.split()[0] == "DISCONNECT":
        reqHandlers.disconnectGroup(self, groups, groupsLock, message.split()[2])

    elif message == "PEER DISCONNECT":
        reqHandlers.peerDisconnection(self, groups, groupsLock, peers)

    elif message == "BYE":
        answer = "BYE PEER"
        transmission.mySend(self.client_sock, answer)
        self.stop()

    else:
        answer = "ERROR - UNEXPECTED MESSAGE"
        transmission.mySend(self.client_sock, answer)


if __name__ == '__main__':
    """main function, starts the server"""
    initServer()

    myIP = socket.gethostbyname(socket.gethostname())
    port = 45154
    server = Server(myIP,port)