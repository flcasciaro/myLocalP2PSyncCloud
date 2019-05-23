import socket

BUFSIZE = 4096
SIZE_LENGTH = 16

TIMEOUT = 3.0

def mySend(sock, data):
    """wrapper for the send function"""

    if sock is None:
        return

    sock.settimeout(TIMEOUT)

    "data is a string message"
    data = str(data).encode('utf-8')
    size = len(data)

    # print("data: ", data)
    # print("size: ", size)

    """put size on a 16 byte string"""
    strSize = str(size).zfill(SIZE_LENGTH)
    strSize = strSize.encode('utf-8')

    # print("strSize: ", strSize)

    """send the size of the following data"""
    totalSent = 0
    while totalSent < SIZE_LENGTH:
        try:
            sent = sock.send(strSize[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("sock connection broken")
        totalSent = totalSent + sent

    # print("strSize sent")

    """send data"""
    totalSent = 0
    while totalSent < size:
        try:
            sent = sock.send(data[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("sock connection broken")
        totalSent = totalSent + sent

    # print("data sent")


def myRecv(sock):
    """wrapper for the recv function"""

    if sock is None:
        return None

    sock.settimeout(TIMEOUT)

    """read the 16 byte string representing the data size"""
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

    dataSize = int(''.join(chunks))
    # print("datasize", dataSize)

    """read data"""
    chunks = []
    bytesRec = 0
    while bytesRec < dataSize:
        try:
            chunk = sock.recv(min(dataSize - bytesRec, BUFSIZE))
        except socket.timeout:
            raise socket.timeout

        if chunk == '':
            raise RuntimeError("sock connection broken")
        # print(chunk)
        bytesRec += len(chunk)
        chunks.append(chunk.decode('utf-8'))

    data = ''.join(chunks)
    # print("data", data)
    return str(data)