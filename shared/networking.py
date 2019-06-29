"""
Project: myP2PSync
This code manages all the networking functions of myP2PSync.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""

import os
import socket

# ZeroTier myP2PSync network ID
networkID = "e5cd7a9e1cf88a16"

# temporary filename
zeroTierFile = "tmpZerotier.txt"

# constants used in send/receive data over sockets
SIZE_LENGTH = 16
BUFSIZE = 4096
TIMEOUT = 3.0


def getMyIP():
    """
    Retrieve the IP of the machine.
    If the machine is inside a private network
    the private address is retrieved.
    :return: an IP address
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 1))  # connect() for UDP doesn't send packets
    return s.getsockname()[0]


def joinNetwork():
    """
    Machine joins the ZeroTier myP2PSync network using the zerotier-cli interface.
    :return: ZeroTier IP address of the machine
    """
    # join the network
    cmd = "zerotier-cli join {}".format(networkID)
    os.system(cmd)

    # ZeroTier sometimes takes a bit of time to register the peer
    # before that moment the listnetworks command is not valid
    # so this while goes on until the subscription is recorded
    # and listnetworks has a correct output
    while True:
        # print zerotier list of networks into a temp file
        cmd = "zerotier-cli listnetworks > {}".format(zeroTierFile)
        os.system(cmd)

        # obtain the generated zerotier IP
        zeroTierIP = None
        f = open(zeroTierFile, "r")
        for line in f:
            lineSplit = line.split()
            try:
                if lineSplit[0] == "200" and lineSplit[2] == networkID:
                    # ZeroTier IP of the machine is the last parameter of the line
                    zeroTierIP = lineSplit[-1].split("/")[0]
                    break
            except IndexError:
                continue
        f.close()
        if zeroTierIP != '-' and zeroTierIP is not None:
            print("Obtained {} address from ZeroTier".format(zeroTierIP))
            # remove temp file
            os.remove(zeroTierFile)
            break

    return zeroTierIP


def leaveNetwork():
    """
    Machine leaves the ZeroTier myP2PSync network using the zerotier-cli interface.
    :return: void
    """
    cmd = "zerotier-cli leave {}".format(networkID)
    os.system(cmd)


def createConnection(addr):
    """
    Create a socket connection with a remote host.
    In case of success return the established socket.
    In case of failure (timeout or connection refused) return None.
    :param addr: address (IP, port) of the remote host.
    :return: socket object or None
    """

    # cast port number to integer
    addr = (addr[0],int(addr[1]))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(addr)
    except (socket.timeout, ConnectionRefusedError):
        return None
    return s


def closeConnection(s, peerID):
    """
    Wrapper function for socket.close().
    Coordinates the socket close operation with the remote host.
    Send a BYE message and wait for a reply.
    Finally close the socket.
    :param s: socket which will be closed
    :param peerID: id of the peer sending the closing message
    :return: void
    """

    try:
        # send BYE message
        message = str(peerID) + " " + "BYE"
        mySend(s, message)
        # get the answer into an "ignore" variable
        __ = myRecv(s)
    except (socket.timeout, RuntimeError):
        pass

    # close the socket
    s.close()


def mySend(sock, data):
    """
    Send a message on the socket.
    :param sock: socket connection object
    :param data: data that will be sent
    :return: void
    """

    # check socket object validity
    if sock is None:
        return

    # set a timeout
    sock.settimeout(TIMEOUT)

    # data is a string message: it needs to be converted to bytes
    data = str(data).encode('utf-8')

    # get size of the message
    size = len(data)

    # put size on a 16 byte string filled with 0s
    # e.g. size = 123
    #      strSize = 0000000000000123
    strSize = str(size).zfill(SIZE_LENGTH)
    strSize = strSize.encode('utf-8')

    # send the size of the data
    totalSent = 0
    while totalSent < SIZE_LENGTH:
        try:
            sent = sock.send(strSize[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("sock connection broken")
        totalSent = totalSent + sent

    # send data
    totalSent = 0
    while totalSent < size:
        try:
            sent = sock.send(data[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("sock connection broken")
        totalSent = totalSent + sent


def myRecv(sock):
    """
    Wrapper for the recv function.
    :param sock: socket connection object
    :return: data received
    """

    # check socket object validity
    if sock is None:
        return None

    # set a timeout
    sock.settimeout(TIMEOUT)

    # read the 16 byte string representing the data size
    chunks = list()
    bytesRec = 0
    while bytesRec < SIZE_LENGTH:
        try:
            chunk = sock.recv(min(SIZE_LENGTH - bytesRec, SIZE_LENGTH))
        except socket.timeout:
            raise socket.timeout
        if chunk == '':
            raise RuntimeError("sock connection broken")
        bytesRec += len(chunk)
        chunks.append(chunk.decode('utf-8'))

    # eventually join chunks
    dataSize = int(''.join(chunks))

    # read data until dataSize bytes have been received
    chunks = list()
    bytesRec = 0
    while bytesRec < dataSize:
        try:
            chunk = sock.recv(min(dataSize - bytesRec, BUFSIZE))
        except socket.timeout:
            raise socket.timeout

        if chunk == '':
            raise RuntimeError("sock connection broken")
        bytesRec += len(chunk)
        chunks.append(chunk.decode('utf-8'))

    # eventually join chunks
    data = ''.join(chunks)

    return str(data)


def sendChunk(sock, chunk, chunkSize):
    """
    Send a file chunk over a socket connection.
    :param sock: socket connection object
    :param chunk: bytes that will be sent
    :param chunkSize: number of bytes that will be sent
    :return: void
    """

    # check socket object validity
    if sock is None:
        return

    # set a timeout
    sock.settimeout(TIMEOUT)

    # send data until chunkSize bytes have been sent
    totalSent = 0
    while totalSent < chunkSize:
        try:
            sent = sock.send(chunk[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("sock connection broken")
        totalSent = totalSent + sent


def recvChunk(sock, chunkSize):
    """
    Receive a file chunk over a socket connection.
    :param sock: socket connection object
    :param chunkSize: number of bytes that will be received
    :return: data received representing the file chunk
    """

    # check socket object validity
    if sock is None:
        return

    pieces = list()
    bytesRec = 0

    # read on the socket until chunkSize bytes have been received
    while bytesRec < chunkSize:
        try:
            piece = sock.recv(min(chunkSize - bytesRec, BUFSIZE))
        except socket.timeout:
            raise socket.timeout

        if piece == b'':
            raise RuntimeError("sock connection broken")
        bytesRec += len(piece)
        pieces.append(piece)

    # join chunk pieces
    chunk = b''.join(pieces)

    return chunk
