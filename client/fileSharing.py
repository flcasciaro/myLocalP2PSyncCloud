"""This file contains all the code necessary to handle the files-sharing"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import os
import shutil
import time
from random import randint, random
from threading import Thread

import peerCore
import transmission

MAX_UNAVAILABLE = 5

MAX_THREADS = 5
MAX_CHUNKS_PER_THREAD = 20


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

    # print("asking with my chunk list: " + answer)
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

                        answer = "OK - I'M SENDING IT"
                        transmission.mySend(thread.client_sock, answer)
                        time.sleep(1)
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

                        answer = "OK - I'M SENDING IT"
                        transmission.mySend(thread.client_sock, answer)
                        time.sleep(1)
                        transmission.sendChunk(thread.client_sock, dataChunk, chunkSize)

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
        # print("asking with: " + answer)
        transmission.mySend(thread.client_sock, answer)



def downloadFile(file):
    print("Starting synchronization of", file.filename)

    key = file.groupName + "_" + file.filename

    file.syncLock.acquire()

    file.initDownload()

    unavailable = 0

    # ask for the missing peers while the missing list is not empty
    while len(file.missingChunks) > 0 and unavailable < MAX_UNAVAILABLE:

        peerCore.syncThreadsLock.acquire()
        if peerCore.syncThreads[key]["stop"]:
            peerCore.syncThreadsLock.release()
            unavailable = MAX_UNAVAILABLE
            break
        else:
            peerCore.syncThreadsLock.release()


        # retrieve the list of active peers for the file
        activePeers = peerCore.retrievePeers(file.groupName, selectAll=False)

        if activePeers is None:
            # error occurred while asking the peers list to the server
            unavailable += 1
            time.sleep(1)
            continue


        if len(activePeers) == 0:
            # Empty list retrieved: no active peers for that group
            unavailable += 1
            time.sleep(1)
            continue

        """
        chunks_peers is a dictionary where key is the chunkID and
        value is the list of peer which have that chunk
        """
        chunks_peers = dict()

        """
        chunksCounter is a dictionary where key is the chunkID and
        value is the number of peers having that chunk
        """
        chunksCounter = dict()

        for peer in activePeers:
            """
            ask each peer which chunks it has and collect informations
            in order to apply the rarest-first approach
            """

            chunksList = getChunksList(file, peer["peerIP"], peer["peerPort"])

            # clean the list from already available chunks
            for chunk in file.availableChunks:
                if chunk in chunksList:
                    chunksList.remove(chunk)

            if chunksList is not None:

                for chunk in chunksList:
                    if chunk in chunksCounter:
                        chunksCounter[chunk] += 1
                        chunks_peers[chunk].append(peer)
                    else:
                        chunksCounter[chunk] = 1
                        chunks_peers[chunk] = list()
                        chunks_peers[chunk].append(peer)

        if len(chunksCounter) == 0:
            # active peers don't have missing chunks
            unavailable += 1
            time.sleep(1)
            continue

        if len(activePeers) >= MAX_THREADS:
            numThreads = MAX_THREADS
        else:
            numThreads = len(activePeers)

        busyPeers = list()
        threadInfo = list()

        busyThreads = 0
        chunksReady = 0

        for i in range(0, numThreads):
            threadInfo.append(dict())
            threadInfo[i]["peer"] = None
            threadInfo[i]["chunksList"] = list()

        threshold = 0.5

        for chunk in sorted(chunksCounter, key=chunksCounter.get):

            #generate a value between 0 and 1
            p = random()

            if p > threshold:
                # randomly discard this chunk
                continue

            if chunksReady == (numThreads * MAX_CHUNKS_PER_THREAD):
                # all the chunk lists have been filled completely
                break

            found = False

            # try to insert in one of the previous peer chunks list
            for i in range(0, busyThreads):
                if threadInfo[i]["peer"] is None:
                    break
                if threadInfo[i]["peer"] in chunks_peers[chunk]:
                    if len(threadInfo[i]["chunksList"]) < MAX_CHUNKS_PER_THREAD:
                        threadInfo[i]["chunksList"].append(chunk)
                        chunksReady += 1
                        found = True
                        break

            if found:
                continue

            if busyThreads == numThreads:
                # go to next chunks because no thread is available for the current one
                # and cannot add another thread
                continue

            # choose a random peer from the list
            r = randint(0, len(chunks_peers[chunk]) - 1)
            i = 0

            while i <= (len(chunks_peers[chunk]) - 1):
                selectedPeer = chunks_peers[chunk][r]
                if selectedPeer not in busyPeers:
                    threadInfo[busyThreads]["peer"] = selectedPeer
                    threadInfo[busyThreads]["chunksList"] = list()
                    threadInfo[busyThreads]["chunksList"].append(chunk)
                    busyThreads += 1
                    chunksReady += 1
                    busyPeers.append(selectedPeer)
                    break
                else:
                    # the thread associate to the peer has reached MAX_CHUNKS_PER_THREAD size list
                    r = (r + 1) % len(chunks_peers[chunk])
                    i += 1

        threads = list()

        # start threads
        for i in range(0, busyThreads):
            threadChunksList = threadInfo[i]["chunksList"]
            peerIP = threadInfo[i]["peer"]["peerIP"]
            peerPort = threadInfo[i]["peer"]["peerPort"]

            t = Thread(target=getChunk, args=(file, threadChunksList, peerIP, peerPort))
            threads.append(t)
            t.start()

        # wait for threads termination
        for i in range(0, busyThreads):
            threads[i].join()

        threshold += 0.1

        file.setProgress()


    if unavailable == MAX_UNAVAILABLE:
        # save download current state in order to restart it at next sync
        file.previousChunks = file.availableChunks
        file.syncLock.release()
        print("Synchronization of {} failed".format(file.filename))
        peerCore.syncThreadsLock.acquire()
        del peerCore.syncThreads[key]
        peerCore.syncThreadsLock.release()
        return

    if mergeChunks(file):
        # if mergeChunks succeeds clean the download current state
        file.status = "S"
        file.previousChunks = list()
    else:
        # if mergeChunks fails save the download current state
        file.previousChunks = file.availableChunks

    peerCore.syncThreadsLock.acquire()
    del peerCore.syncThreads[key]
    peerCore.syncThreadsLock.release()

    file.syncLock.release()



def getChunksList(file, peerIP, peerPort):
    chunksList = list()

    key = file.groupName + "_" + file.filename

    s = peerCore.createSocket(peerIP, peerPort)
    if s is None:
        return None

    message = "CHUNKS_LIST {} {}".format(key, file.timestamp)
    transmission.mySend(s, message)

    data = transmission.myRecv(s)
    # print('Received from the peer :', data)

    peerCore.closeSocket(s)

    if str(data).split()[0] == "ERROR":
        # return empty list
        return chunksList
    else:
        chunksList = eval(str(data))
        return chunksList


def getChunk(file, chunksList, peerIP, peerPort):

    print(chunksList)

    for chunkID in chunksList:

        s = peerCore.createSocket(peerIP, peerPort)
        if s is None:
            return

        key = file.groupName + "_" + file.filename

        if chunkID == file.chunksNumber - 1:
            chunkSize = file.lastChunkSize
        else:
            chunkSize = file.chunksSize

        message = "CHUNK {} {} {}".format(key, file.timestamp, chunkID)
        transmission.mySend(s, message)
        answer = transmission.myRecv(s)
        print(answer)
        if answer.split(" ")[0] == "ERROR":
            peerCore.closeSocket(s)
            continue
        time.sleep(1)
        data = transmission.recvChunk(s, chunkSize)
        #print('Received from the peer :', data)

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

            file.missingChunks.remove(chunkID)
            file.availableChunks.append(chunkID)

            file.fileLock.release()

        except FileNotFoundError:
            file.fileLock.release()





def mergeChunks(file):
    """

    :param file:
    :return:
    """

    newFilePath = getNewFilePath(file)
    tmpDirPath = getTmpDirPath(file)

    # merge chunks writing each chunks in the new file
    try:
        f1 = open(newFilePath, 'wb')
        for chunkID in range(0, file.chunksNumber):
            chunkPath = tmpDirPath + "chunk" + str(chunkID)
            with open(chunkPath, 'rb') as f2:
                f1.write(f2.read())
    except FileNotFoundError:
        print("Error while creating the new file")
        return False

    # remove previous version of the file (if any)
    if os.path.exists(file.filepath):
        os.remove(file.filepath)

    os.rename(newFilePath, file.filepath)

    # remove chunks directory
    shutil.rmtree(tmpDirPath)

    # force timestamp to syncBeginningTime timestamp
    os.utime(file.filepath, (file.timestamp, file.timestamp))

    print("Chunks of {} successfully merged".format(file.filename))


def getNewFilePath(file):
    """
    Build the newFilePath
           ex.
           file.filepath = home/prova.txt
           filenameWE = prova
           fileExtension = splitFilename[1] = txt
           dirPath = home/
           newFilePath = home/prova_new.txt
    :param file: File object
    :return: string representing the path
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
    Build the new temporary directory paths
               ex.
               file.filepath = home/prova.txt
               filenameWE = prova
               fileExtension = splitFilename[1] = txt
               dirPath = home/
               tmpDirPath = home/prova_new_tmp/
    :param file: File object
    :return: string representing the path
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
