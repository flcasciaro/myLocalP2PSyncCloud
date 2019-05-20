BUFSIZE = 4096
SIZE_LENGTH = 16


def mySend(socket, data):
    """wrapper for the send function"""

    socket.setTimeout(3)

    "data is a string message"
    data = str(data).encode('ascii')
    size = len(data)

    # print("data: ", data)
    # print("size: ", size)

    """put size on a 16 byte string"""
    strSize = str(size).zfill(SIZE_LENGTH)
    strSize = strSize.encode('ascii')

    # print("strSize: ", strSize)

    """send the size of the following data"""
    totalSent = 0
    while totalSent < SIZE_LENGTH:
        try:
            sent = socket.send(strSize[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent

    # print("strSize sent")

    """send data"""
    totalSent = 0
    while totalSent < size:
        try:
            sent = socket.send(data[totalSent:])
        except socket.timeout:
            raise socket.timeout
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalSent = totalSent + sent

    # print("data sent")


def myRecv(socket):
    """wrapper for the recv function"""

    socket.setTimeout(3)

    """read the 16 byte string representing the data size"""
    chunks = []
    bytesRec = 0
    while bytesRec < SIZE_LENGTH:
        try:
            chunk = socket.recv(min(SIZE_LENGTH - bytesRec, SIZE_LENGTH))
        except socket.timeout:
            raise socket.timeout
        if chunk == '':
            raise RuntimeError("Socket connection broken")
        bytesRec += len(chunk)
        chunks.append(chunk.decode('ascii'))

    dataSize = int(''.join(chunks))
    # print("datasize", dataSize)

    """read data"""
    chunks = []
    bytesRec = 0
    while bytesRec < dataSize:
        try:
            chunk = socket.recv(min(dataSize - bytesRec, BUFSIZE))
        except socket.timeout:
            raise socket.timeout

        if chunk == '':
            raise RuntimeError("Socket connection broken")
        # print(chunk)
        bytesRec += len(chunk)
        chunks.append(chunk.decode('ascii'))

    data = ''.join(chunks)
    # print("data", data)
    return str(data)