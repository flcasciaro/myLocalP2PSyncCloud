"""This file contains all the code necessary to handle the files-sharing"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import base64
import os
import time
from random import randint

import peerCore
import transmission


def sendChunksList(message, thread, localFileList):

    messageFields = message.split()
    key = messageFields[1]
    lastModified = messageFields[2] + " " + messageFields[3]

    if key in localFileList:
        if localFileList[key].lastModified == lastModified:

            answer = str(localFileList[key].availableChunks)

        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED KEY {}".format(key)

    print("asking with my chunk list: " + answer)
    transmission.mySend(thread.client_sock, answer)

def sendChunk(message, thread, localFileList):

    messageFields = message.split()
    key = messageFields[1]
    lastModified = messageFields[2] + " " + messageFields[3]
    chunkID = messageFields[4]

    print("************************************")
    print("chunkID: ", chunkID)
    print("************************************")

    answer = None

    if key in localFileList:
        file = localFileList[key]
        print(file)
        print(file.lastModified)
        print(lastModified)
        if file.lastModified == lastModified:
            if chunkID in file.availableChunks:

                if chunkID == file.chunksNumber - 1:
                    chunkSize = file.lastChunkSize
                else:
                    chunkSize = file.chunksSize

                print(chunkSize)

                print("*******************************file status: ",file.status)

                if file.status == "S":
                    """peer has the whole file -> open and send it"""
                    print("here")
                    try:
                        file.fileLock.acquire()
                        print("here1")
                        f = open(file.filepath, 'rb')
                        print("here2")
                        offset = chunkID * file.chunksSize
                        f.seek(offset)
                        print("here3")
                        dataChunk = f.read(chunkSize)
                        encodedChunk = base64.b64encode(dataChunk)

                        print("************************************")
                        print(encodedChunk)
                        print("************************************")

                        transmission.mySend(thread.client_sock, encodedChunk)

                        f.close()
                        file.fileLock.release()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
                        file.fileLock.release()


                if file.status == "D":
                    """peer is still downloading the file -> send chunk from tmp file"""

                    try:
                        file.fileLock.acquire()

                        chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)

                        f = open(chunkPath, 'rb')

                        dataChunk = f.read(chunkSize)
                        encodedChunk = base64.b64encode(dataChunk)

                        transmission.mySend(thread.client_sock, encodedChunk)

                        f.close()
                        file.fileLock.release()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
                        file.fileLock.release()
            pass

        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED KEY {}".format(key)

    if answer is not None:
        print("asking with: " + answer)
        transmission.mySend(thread.client_sock, answer)



def downloadFile(file):

    print("Starting synchronization of", file.filename)

    file.syncLock.acquire()

    file.initDownload()

    unavailable = 0

    # ask for the missing peers while the missing list is not empty
    while len(file.missingChunks) > 0 and unavailable < 5:

        """retrieve the list of active peers for the file"""
        activePeers = peerCore.retrievePeers(file.groupName, selectAll=False)

        if activePeers is None:
            """error occurred while asking the peers list to the server"""
            time.sleep(3)
            unavailable += 1
            continue
        else:
            """"Empty list retrieved: no active peers for that group"""
            if len(activePeers) == 0:
                time.sleep(3)
                unavailable += 1
                continue

        print(activePeers)

        """chunks_peers is a dictionary where key is the chunkID and
        value is the list of peer which have that chunk"""
        chunks_peers = dict()
        """chunksCounter is a dictionary where key is the chunkID and
        value is the number of peers having that chunk"""
        chunksCounter = dict()

        for peer in activePeers:
            """ask each peer which chunks it has and collect informations
            in order to apply the rarest-first approach"""

            #print(peer)

            chunksList = getChunksList(file, peer["peerIP"], peer["peerPort"])

            if chunksList is not None:

                for chunk in chunksList:
                    if chunk in chunksCounter:
                        chunksCounter[chunk] += 1
                        chunks_peers[chunk].append(peer)
                    else:
                        chunksCounter[chunk] = 1
                        chunks_peers[chunk] = list()
                        chunks_peers[chunk].append(peer)

        """ask for the 10 rarest chunks"""
        i = 0
        askFor = 10

        for chunk in sorted(chunksCounter, key=chunksCounter.get):

            if len(file.missingChunks) == 0:
                break

            if chunksCounter[chunk] == 0 :
                """it's impossible to download the file because the seed is unactive 
                and the other peers don't have chunks yet"""
                unavailable += 1
                break

            if chunk in file.missingChunks:

                """choose a random peer from the list"""
                r = randint(0, len(chunks_peers[chunk]) - 1)

                peerIP = chunks_peers[chunk][r]["peerIP"]
                peerPort = chunks_peers[chunk][r]["peerPort"]

                if getChunk(file, chunk, peerIP, peerPort):
                    i += 1
                    if i >= askFor:
                        break

        file.setProgress()

        del chunksCounter
        del chunks_peers

    if unavailable == 4:
        file.syncLock.release()
        return

    if mergeChunk(file):
        file.status = "S"

    file.syncLock.release()

def getChunksList(file, peerIP, peerPort):

    chunksList = list()

    key = file.groupName + "_" + file.filename

    s = peerCore.createSocket(peerIP, peerPort)

    message = "CHUNKS_LIST {} {}".format(key, file.lastModified)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the peer :', str(data))

    peerCore.closeSocket(s)

    if str(data).split()[0] == "ERROR":
        #return empty list
        return chunksList
    else:
        chunksList = eval(str(data))
        return chunksList



def getChunk(file, chunkID, peerIP, peerPort):

    s = peerCore.createSocket(peerIP, peerPort)

    key = file.groupName + "_" + file.filename

    message = "CHUNK {} {} {}".format(key, file.lastModified, chunkID)
    transmission.mySend(s, message)

    encodedData = transmission.myRecv(s)
    # print('Received from the peer :', str(data))

    peerCore.closeSocket(s)

    data = base64.b64decode(encodedData)

    try:
        file.fileLock.acquire()

        if not os.path.exists(file.filepath + "_tmp"):
            print("creating the path: " + file.filepath + "_tmp")
            os.makedirs(file.filepath + "_tmp")

        chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)

        f = open(chunkPath, 'wb')

        f.write(data)

        f.close()
        file.fileLock.release()
    except FileNotFoundError:
        file.fileLock.release()
        return False


    file.missingChunks.remove(chunkID)
    file.availableChunks.append(chunkID)

    return True


def mergeChunk(file):

    print("merging chunk")

    newPath = file.filepath + "_new"

    try:
        f1 = open(newPath, 'wb')
        for chunkID in range(0, file.chunksNumber):
            chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)
            with open(chunkPath, 'rb') as f2:
                f1.write(f2.read())
    except FileNotFoundError:
        print("Error while creating the new file")
        return False

    os.remove(file.filepath)
    os.rename(newPath, file.filepath)

    os.shutil.rmtree(file.filepath + "_tmp")

    #date = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
    modTime = time.mktime(file.lastModified)

    os.utime(file.filepath, (modTime, modTime))


