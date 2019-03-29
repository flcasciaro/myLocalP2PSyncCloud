"""Server of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import select
import socket
from threading import Thread

"""Main data structure for groups management
It's a dictionary where the key is the GroupName and the value is
another dictionary containing information about the group e.g. tokens, peers"""
groups = dict()

"""Main data structure for peers management
It's a dictionary where the key is the combination peerIP+peerPort and the value is
another dictionary containing information about the peer e.g. list of groups,
where for each group we have a dictionary with the information about role and status"""
peers = dict()


stop = None

# database for an initial load of the data about bins/waste containers
db_path = 'init.db'

def initServer():
    """Initialize server data structures
    Data structures are filled with data read from local text files if they exist"""


    with open('groups.txt', 'r') as f:

        for line in f:
            groupInfo = line.split()
            groupInfoDict = dict()
            groupInfoDict["name"] = groupInfo[0]
            groupInfoDict["tokenRW"] = groupInfo[1]
            groupInfoDict["tokenRO"] = groupInfo[2]
            groupInfoDict["total"] = groupInfo[3]
            groupInfoDict["active"] = 0
            groupInfoDict["peers"] = list()
            groups[groupInfo[0]] = groupInfoDict

    with open('peers.txt', 'r') as f:

        for line in f:
            peerInfo = line.split()
            """peerInfo[0]+":"+peerInfo[1] is something like 192.168.0.1:5200 (IP:Port)
            If this string is not present in the dictionary this is the first time I find
            this peer in the file, I need to initialize the list of groups"""
            peerID = peerInfo[0]+":"+peerInfo[1]
            if peerID not in peers:
                peers[peerID] = dict()
                peers[peerID]["peerIP"] = peerInfo[0]
                peers[peerID]["peerPort"] = peerInfo[1]
                peers[peerID]["groups"] = list()
            peerGroup = dict()
            peerGroup["groupName"] = peerInfo[2]
            peerGroup["role"] = peerInfo[3]
            peerGroup["active"] = False
            peers[peerID]["groups"].append(peerGroup)

def saveState():
    """Save the state of groups and peers in order to allow to restore the session in future"""
    with open('groups.txt', 'w') as f:
        for group in groups.values():
            f.write(group["name"]+" "+
                    group["tokenRW"]+" "+
                    group["tokenRO"]+" "+
                    group["total"]+"\n")

    with open('peers.txt', 'w') as f:
        for peer in peers.values():
            for group in peer["groups"]:
                f.write(peer["peerIP"]+" "+
                        peer["peerPort"]+" "+
                        group["groupName"]+" "+
                        group["role"]+"\n")


def startServer(host = '0.0.0.0', port = 2010, max_clients = 10):

    """ Initialize the server with a host and port to listen to.
    Provide a list of functions that will be used when receiving specific data """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(max_clients)
    sock_threads = []
    counter = 0 # Will be used to give a number to each thread


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
    stop = True


class SocketServerThread(Thread):
    def __init__(self, client_sock, client_addr, number):
        """ Initialize the Thread with a client socket and address """
        Thread.__init__(self)
        self.client_sock = client_sock
        self.client_addr = client_addr
        self.number = number
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
                    read_data = self.client_sock.recv(255)

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


def removeToken(group):
    """"This function return a group dictionary without the token field"""
    modGroup = group
    del modGroup["token"]
    return modGroup


def manageRequest(self, message):

    """Serves the client request"""
    print('[Thr {}] Received {}'.format(self.number, message))

    if message == "SEND PREVIOUS GROUPS LIST":
        gl = list()
        for group in groupList:
            gl.append(removeToken(group))
        self.client_sock.send(str(gl).encode('ascii'))

        read_data = self.client_sock.recv(255)
        request = read_data.decode('ascii').rstrip().split()
        print(request)
        groupName = request[1]
        groupToken = request[3]

        if groupName in groupDict:
            if groupDict[groupName] == groupToken:
                message = "GROUP JOINED"
            else:
                message = "ACCESS DENIED"
        else:
            message = "ACCESS DENIED"

        self.client_sock.send(message.encode('ascii'))
    elif message == "SEND OTHER GROUPS LIST":
        pass
    elif message.split()[0] == "RESTORE":
        pass
    elif message.split()[0] == "JOIN":
        pass
    elif message == "BYE":
        message = "BYE CLIENT"
        self.client_sock.send(message.encode('ascii'))
        self.stop()
    else:
        message = "WTF_U_WANT"
        self.client_sock.send(message.encode('ascii'))

if __name__ == '__main__':
    """main function, starts the server"""

    initServer()
    stop = False
    #startServer()

    #server stopped
    saveState()

