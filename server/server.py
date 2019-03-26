"""Server of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import argparse
import select
import socket
from threading import Thread

"""main data structure for groups list"""
groupList = list()
"""additional data structure useful for a fast access operation
key = Group Name, value = group Token"""
groupDict = dict()

def get_args():
    """
    Get command line args from the user.
    """
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to Central Index Server')
    parser.add_argument('-p', '--port',
                        type=int,
                        required=True,
                        action='store',
                        help='Server Port Number')
    parser.add_argument('-r', '--replica',
                        type=int,
                        default=1,
                        action='store',
                        help='Data Replication Factor')
    args = parser.parse_args()
    return args

def serverInit():
    """Initialize server configuration and data structures
    Data structures are filled with data read from configuration files / local database"""

    with open('grouplist.txt', 'r') as f:

        for line in f:
            groupInfo = line.split()
            groupInfoDict = dict()
            groupInfoDict["id"] = groupInfo[0]
            groupInfoDict["name"] = groupInfo[1]
            groupInfoDict["token"] = groupInfo[2]
            groupInfoDict["active"] = groupInfo[3]
            groupInfoDict["total"] = groupInfo[4]
            groupList.append(groupInfoDict)
            groupDict[groupInfoDict["name"]]= groupInfoDict["token"]



class SocketServer(Thread):
    def __init__(self, host = '0.0.0.0', port = 2010, max_clients = 10):
        """ Initialize the server with a host and port to listen to.
        Provide a list of functions that will be used when receiving specific data """
        Thread.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host = host
        self.port = port
        self.sock.bind((host, port))
        self.sock.listen(max_clients)
        self.sock_threads = []
        self.counter = 0 # Will be used to give a number to each thread
        self.__stop = False

    def close(self):
        """ Close the client socket threads and server socket if they exists. """
        print('Closing server socket (host {}, port {})'.format(self.host, self.port))

        for thr in self.sock_threads:
            thr.stop()
            thr.join()

        if self.sock:
            self.sock.close()
            self.sock = None

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
        self.close()

    def stop(self):
        """To be called in order to stop the server (press X in the GUI or in order to manage error)
        If called self.__stop is set to True and self.close() is called"""
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

    if message == "SEND GROUPS LIST":
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
                message = "Access Conceded"
            else:
                message = "Access Denied"
        else:
            message = "Access Denied"

        self.client_sock.send(message.encode('ascii'))



    elif message == "BYE":
        message = "bye client"
        self.client_sock.send(message.encode('ascii'))
        self.stop()
    else:
        message = "hello client"
        self.client_sock.send(message.encode('ascii'))

def main():
    """main function, starts the server"""

    #args = get_args()

    serverInit()

    server = SocketServer()
    server.start()


main()

