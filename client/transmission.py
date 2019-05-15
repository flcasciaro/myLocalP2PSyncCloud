BUFSIZE = 4096
SIZE_LENGTH = 16

def mySend(socket, data, size):
    """"""

    """put size on a 16 byte string"""
    strSize = str(size).zfill(SIZE_LENGTH)

    """send the size of the following data"""
    totalSent = 0
    while totalSent < SIZE_LENGTH:
        sent = socket.send(strSize[totalSent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent

    """send data"""
    totalSent = 0
    while totalSent < size:
        sent = socket.send(data[totalSent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent


def myRecv(socket):

    chunks = []
    bytesRec = 0
    while bytesRec < SIZE_LENGTH:
        chunk = socket.recv(min(SIZE_LENGTH - bytesRec, SIZE_LENGTH))
        if chunk == '':
            raise RuntimeError("Socket connection broken")
        chunks.append(chunk)
        bytesRec += len(chunk)

    dataSize = int(''.join(chunks))

    chunks = []
    bytesRec = 0
    while bytesRec < SIZE_LENGTH:
        chunk = socket.recv(min(dataSize - bytesRec, BUFSIZE))
        if chunk == '':
            raise RuntimeError("Socket connection broken")
        chunks.append(chunk)
        bytesRec += len(chunk)

    data = ''.join(chunks)
    return data