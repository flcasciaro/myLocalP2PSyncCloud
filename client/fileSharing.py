"""This file contains all the code necessary to handle the files-sharing"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import os
import shutil
from random import randint

import peerCore
import transmission


def sendChunksList(message, thread, localFileList):

    messageFields = message.split()
    key = messageFields[1]
    timestamp = int(messageFields[2])

    if key in localFileList:
        if localFileList[key].timestamp == timestamp:

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
    timestamp = int(messageFields[2])
    chunkID = int(messageFields[3])

    answer = None

    if key in localFileList:
        file = localFileList[key]
        if file.timestamp == timestamp:
            if chunkID in file.availableChunks:
                print("*****************setting chunk size")
                if chunkID == file.chunksNumber - 1:
                    chunkSize = file.lastChunkSize
                else:
                    chunkSize = file.chunksSize

                if file.status == "S":
                    """peer has the whole file -> open and send it"""

                    try:
                        file.fileLock.acquire()
                        f = open(file.filepath, 'rb')
                        offset = chunkID * file.chunksSize
                        f.seek(offset)
                        dataChunk = f.read(chunkSize)

                        #encodedChunk = base64.b64encode(dataChunk)

                        print("************************************")
                        print(dataChunk)
                        print("************************************")

                        transmission.sendChunk(thread.client_sock, dataChunk, chunkSize)

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

                        #encodedChunk = base64.b64encode(dataChunk)

                        transmission.mySend(thread.client_sock, dataChunk)

                        f.close()
                        file.fileLock.release()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
                        file.fileLock.release()
            else:
                answer = "ERROR - UNAVAILABLE CHUNK"
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

    unavailable = False

    # ask for the missing peers while the missing list is not empty
    while len(file.missingChunks) > 0 and not unavailable:

        """retrieve the list of active peers for the file"""
        activePeers = peerCore.retrievePeers(file.groupName, selectAll=False)

        if activePeers is None:
            """error occurred while asking the peers list to the server"""
            unavailable = True
            continue
        else:
            """"Empty list retrieved: no active peers for that group"""
            if len(activePeers) == 0:
                unavailable = True
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

    if unavailable:
        file.syncLock.release()
        return

    if mergeChunk(file):
        file.status = "S"

    file.syncLock.release()

def getChunksList(file, peerIP, peerPort):

    chunksList = list()

    key = file.groupName + "_" + file.filename

    s = peerCore.createSocket(peerIP, peerPort)

    message = "CHUNKS_LIST {} {}".format(key, file.timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    print('Received from the peer :', data)

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

    if chunkID == file.chunksNumber - 1:
        chunkSize = file.lastChunkSize
    else:
        chunkSize = file.chunksSize

    message = "CHUNK {} {} {}".format(key, file.timestamp, chunkID)
    transmission.mySend(s, message)

    data = transmission.recvChunk(s, chunkSize)
    print('Received from the peer :', data)

    peerCore.closeSocket(s)

    tmpDirPath = getTmpDirPath(file)

    try:
        file.fileLock.acquire()

        if not os.path.exists(tmpDirPath):
            print("creating the path: " + tmpDirPath)
            os.makedirs(tmpDirPath)

        chunkPath = tmpDirPath + "chunk" + str(chunkID)

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

    newFilePath = getNewFilePath(file)
    tmpDirPath = getTmpDirPath(file)

    #merge chunks writing each chunks in the new file
    try:
        f1 = open(newFilePath, 'wb')
        for chunkID in range(0, file.chunksNumber):
            chunkPath = tmpDirPath + "chunk" + str(chunkID)
            with open(chunkPath, 'rb') as f2:
                f1.write(f2.read())
    except FileNotFoundError:
        print("Error while creating the new file")
        return False

    #remove previous version of the file (if any)
    if os.path.exists(file.filepath):
        os.remove(file.filepath)

    os.rename(newFilePath, file.filepath)

    #remove chunks directory
    shutil.rmtree(tmpDirPath)

    #force timestamp to syncBeginningTime timestamp
    os.utime(file.filepath, (file.timestamp, file.timestamp))

def getNewFilePath(file):
    """
        build the newFilePath
           ex.
           file.filepath = home/prova.txt
           filenameWE = prova
           fileExtension = splitFilename[1] = txt
           dirPath = home/
           newFilePath = home/prova_new.txt
    """

    # split filepath into directorypath and filename
    (dirPath, filename) = os.path.split(file.filepath)
    # remove extension from the filename (if any)
    # WoE stands for Without Extension
    splitFilename = filename.split(".")
    filenameWoE = splitFilename[0]

    # path where the file will be merged
    newFilePath = dirPath + "/" + filenameWoE + "_new"
    if len(splitFilename) > 1:
        # concatenate file extension if present
        newFilePath += "."
        newFilePath += splitFilename[1]

    return newFilePath


def getTmpDirPath(file):
    """
            build the new temporary paths
               ex.
               file.filepath = home/prova.txt
               filenameWE = prova
               fileExtension = splitFilename[1] = txt
               dirPath = home/
               tmpDirPath = home/prova_new_tmp/
        """

    # split filepath into directorypath and filename
    (dirPath, filename) = os.path.split(file.filepath)
    # remove extension from the filename (if any)
    # WoE stands for Without Extension
    splitFilename = filename.split(".")
    filenameWoE = splitFilename[0]

    # directory path where the chunks have been stored
    tmpDirPath = dirPath + "/" + filenameWoE + "_tmp/"

    return tmpDirPath


