BUFSIZE = 4096
SIZE_LENGTH = 16


def mySend(socket, data):
    """wrapper for the send function"""

    "data is a string message"
    data = str(data).encode('ascii')
    size = len(data)

    #print("data: ", data)
    #print("size: ", size)

    """put size on a 16 byte string"""
    strSize = str(size).zfill(SIZE_LENGTH)
    strSize = strSize.encode('ascii')

    #print("strSize: ", strSize)

    """send the size of the following data"""
    totalSent = 0
    while totalSent < SIZE_LENGTH:
        sent = socket.send(strSize[totalSent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent

    #print("strSize sent")

    """send data"""
    totalSent = 0
    while totalSent < size:
        sent = socket.send(data[totalSent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent

    #print("data sent")


def myRecv(socket):
    """wrapper for the recv function"""

    """read the 16 byte string representing the data size"""
    chunks = []
    bytesRec = 0
    while bytesRec < SIZE_LENGTH:
        chunk = socket.recv(min(SIZE_LENGTH - bytesRec, SIZE_LENGTH))
        if chunk == '':
            raise RuntimeError("Socket connection broken")
        bytesRec += len(chunk)
        chunks.append(chunk.decode('ascii'))

    dataSize = int(''.join(chunks))
    #print("datasize", dataSize)

    """read data"""
    chunks = []
    bytesRec = 0
    while bytesRec < dataSize:
        chunk = socket.recv(min(dataSize - bytesRec, BUFSIZE))
        if chunk == '':
            raise RuntimeError("Socket connection broken")
        #print(chunk)
        bytesRec += len(chunk)
        chunks.append(chunk.decode('ascii'))

    data = ''.join(chunks)
    #print("data", data)
    return str(data)