"""
Project: myP2PSync
This code handles the server functions of a peer in myP2PSync.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""

import os
import select
import socket
import sys
from threading import Thread

import fileSharing
import syncScheduler

if "networking" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import shared.networking as networking


class Server(Thread):
    """
    Multithread server class that will manage incoming connections.
    For each incoming connection it will create a thread.
    This thread will manage the request and terminate.
    The server runs until the property __stop is equals to False.
    The port on which the server will listen is choosen among available ports.
    """

    def __init__(self, max_clients=5):
        """
        Initialize server.
        :param max_clients: maximum number of incoming connections.
        :return: void
        """
        Thread.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # using port = 0 the server will start on an available port
        self.sock.bind(("0.0.0.0", 0))

        self.host = networking.getMyIP()
        # retrieve selected port
        self.port = self.sock.getsockname()[1]

        self.sock.listen(max_clients)
        self.sockThreads = []

        # give a number to each thread
        self.counter = 0
        self.__stop = False
        self.serverStart = False

    def run(self):
        """
        Accept an incoming connection.
        Start a new SocketServerThread that will handle the communication.
        :return: void
        """

        print('Starting socket server (host {}, port {})'.format(self.host, self.port))
        self.serverStart = True

        while not self.__stop:
            self.sock.settimeout(1)
            try:
                # accept an incoming connection
                clientSock, clientAddr = self.sock.accept()
            except socket.timeout:
                clientSock = None

            if clientSock:
                # create and start a thread that will handle the communication
                clientThr = SocketServerThread(clientSock, clientAddr, self.counter)
                self.counter += 1
                self.sockThreads.append(clientThr)
                clientThr.daemon = True
                clientThr.start()

        self.closeServer()

    def closeServer(self):
        """
        Close the client socket threads and server socket if they exists.
        :return: void
        """

        print('Closing server socket (host {}, port {})'.format(self.host, self.port))

        # wait for running thread termination
        for thr in self.sockThreads:
            thr.stop()
            thr.join()

        if self.sock:
            self.sock.close()

    def stopServer(self):
        """
        This function will be called in order to stop the server
        :return: void
        """

        self.__stop = True


# Thread which will manage an incoming connection and then terminate.
class SocketServerThread(Thread):

    def __init__(self, clientSock, clientAddr, number):
        """
        Initialize the Thread with a client socket and address.
        :return: void
        """

        Thread.__init__(self)
        self.clientSock = clientSock
        self.clientAddr = clientAddr
        self.number = number
        self.__stop = False

    def run(self):
        """
        Run the thread socketServer and manage the incoming communication.
        :return: void
        """

        # print("[Thr {}] SocketServerThread starting with peer {}".format(self.number, self.clientAddr))

        while not self.__stop:
            if self.clientSock:
                # Check if the client is still connected and if data is available:
                try:
                    rdyRead, __, __ = select.select([self.clientSock, ], [self.clientSock, ], [], 5)
                except select.error:
                    print('[Thr {}] Select() failed on socket with {}'.format(self.number, self.clientAddr))
                    self.stop()
                    return

                if len(rdyRead) > 0:
                    # read request
                    readData = networking.myRecv(self.clientSock)

                    # Check if socket has been closed
                    if len(readData) == 0:
                        # print('[Thr {}] {} closed the socket.'.format(self.number, self.clientAddr))
                        self.stop()
                    else:
                        # Strip newlines just for output clarity
                        message = readData.rstrip()
                        messageFields = message.split(' ', 1)
                        peerID = messageFields[0]
                        message = messageFields[1]
                        self.manageRequest(message, peerID)
            else:
                print("[Thr {}] No peer is connected, SocketServer can't receive data".format(self.number))
                self.stop()

        self.close()

    def stop(self):
        """
        Stop the thread socket server.
        :return: void
        """

        self.__stop = True

    def close(self):
        """
        Close connection with the client socket.
        :return: void
        """

        if self.clientSock:
            # print('[Thr {}] Closing connection with {}'.format(self.number, self.clientAddr))
            self.clientSock.close()


    def manageRequest(self, message, peerID):
        """
        Manage different incoming requests.
        Call an appropriate handler according to the message content.
        :param message: incoming message
        :param peerID: id of the peer who sent the message
        :return: void
        """

        action = message.split()[0]

        if action != "BYE":
            print('[Thr {}] [Peer: {}] Received {}'.format(self.number, peerID, message))

        if action == "CHUNKS_LIST":
            fileSharing.sendChunksList(message, self)

        elif action == "CHUNK":
            fileSharing.sendChunk(message, self)

        elif action == "ADDED_FILES":
            answer = syncScheduler.addedFiles(message)
            networking.mySend(self.clientSock, answer)

        elif action == "REMOVED_FILES":
            answer = syncScheduler.removedFiles(message)
            networking.mySend(self.clientSock, answer)

        elif action == "UPDATED_FILES":
            answer = syncScheduler.updatedFiles(message)
            networking.mySend(self.clientSock, answer)

        elif action == "BYE":
            answer = "BYE PEER"
            networking.mySend(self.clientSock, answer)
            self.stop()
