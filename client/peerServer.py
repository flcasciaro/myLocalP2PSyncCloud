import select
import socket
from threading import Thread

import fileSharing
import transmission


class Server(Thread):
    """
    Multithread server class that will manage incoming connections.
    For each incoming connection it will create a thread.
    This thread will manage the request and terminate.
    The server runs until the property __stop is equals to False.
    The port on which the server will listen is choosen among available ports.
    """

    def __init__(self, host, max_clients=5):
        Thread.__init__(self)
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # using port = 0 the server will start on an available port
        self.sock.bind((host, 0))

        # retrieve selected port
        self.port = self.sock.getsockname()[1]

        self.sock.listen(max_clients)
        self.sock_threads = []
        self.counter = 0  # Will be used to give a number to each thread, can be improved (re-assigning free number)
        self.__stop = False
        self.serverStart = False

    def run(self):
        """
        Accept an incoming connection.
        Start a new SocketServerThread that will handle the communication.
        """

        print('Starting socket server (host {}, port {})'.format(self.host, self.port))
        self.serverStart = True

        while not self.__stop:
            self.sock.settimeout(1)
            try:
                # accept an incoming connection
                client_sock, client_addr = self.sock.accept()
            except socket.timeout:
                client_sock = None

            if client_sock:
                # create and start a thread that will handle the communication
                client_thr = SocketServerThread(client_sock, client_addr, self.counter)
                self.counter += 1
                self.sock_threads.append(client_thr)
                client_thr.daemon = True
                client_thr.start()

        self.closeServer()

    def closeServer(self):
        """
        Close the client socket threads and server socket if they exists.
        """

        print('Closing server socket (host {}, port {})'.format(self.host, self.port))

        # wait for running thread termination
        for thr in self.sock_threads:
            thr.stop()
            thr.join()

        if self.sock:
            self.sock.close()

    def stopServer(self):
        """
        This function will be called in order to stop the server
        """

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
        # print("[Thr {}] SocketServerThread starting with peer {}".format(self.number, self.client_addr))

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
                        # print('[Thr {}] {} closed the socket.'.format(self.number, self.client_addr))
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
            # print('[Thr {}] Closing connection with {}'.format(self.number, self.client_addr))
            self.client_sock.close()


def manageRequest(self, message):
    """

    :param self:
    :param message:
    :return:
    """
    # print('[Thr {}] Received {}'.format(self.number, message))

    if message.split()[0] == "CHUNKS_LIST":
        fileSharing.sendChunksList(message, self)

    if message.split()[0] == "CHUNK":
        fileSharing.sendChunk(message, self)

    elif message == "BYE":
        answer = "BYE PEER"
        transmission.mySend(self.client_sock, answer)
        self.stop()