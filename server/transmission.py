"""Code for the transmission of messages and data over socket connection in myP2PSyncCLoud.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import socket

BUFSIZE = 4096
SIZE_LENGTH = 16

TIMEOUT = 3.0


def mySend(sock, data):
    """
    Send a message on the socket
    :param sock: socket connection object
    :param data: data that will be sent
    :return: void
    """

    # check socket object
    if sock is None:
        return

    # set a timeout
    sock.settimeout(TIMEOUT)

    # data is a string message: it needs to be converted to bytes
    data = str(data).encode('utf-8')

    # get size of the message
    size = len(data)

    # put size on a 16 byte string
    strSize = str(size).zfill(SIZE_LENGTH)
    strSize = strSize.encode('utf-8')

    # print("strSize: ", strSize)

    # send the size of the following data
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
    Wrapper for the recv function
    :param sock: socket connection object
    :return: data received
    """

    # check socket object
    if sock is None:
        return None

    # set a timeout
    sock.settimeout(TIMEOUT)

    # read the 16 byte string representing the data size
    chunks = []
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
    chunks = []
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