"""This file contains all the code necessary to handle the files-sharing"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import os
import shutil
import socket
import stat
import time
from random import randint, random
from threading import Thread

import peerCore
import transmission

MAX_UNAVAILABLE = 5

MAX_THREADS = 5
MAX_CHUNKS_PER_THREAD = 50


def sendChunksList(message, thread):
    messageFields = message.split()
    key = messageFields[1]
    timestamp = int(messageFields[2])

    if key in peerCore.localFileList:
        if peerCore.localFileList[key].timestamp == timestamp:
            if peerCore.localFileList[key].availableChunks is not None:
                if len(peerCore.localFileList[key].availableChunks) != 0:
                    answer = str(peerCore.localFileList[key].availableChunks)
                else:
                    answer = "ERROR - EMPTY LIST"
            else:
                answer = "ERROR - NONE LIST"
        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED KEY {}".format(key)

    try:
        transmission.mySend(thread.client_sock, answer)
    except (socket.timeout, RuntimeError):
        return


def sendChunk(message, thread):
    messageFields = message.split()
    key = messageFields[1]
    timestamp = int(messageFields[2])
    chunkID = int(messageFields[3])

    error = True

    if key in peerCore.localFileList:
        file = peerCore.localFileList[key]
        if file.timestamp == timestamp:
            if chunkID in file.availableChunks:

                if chunkID == file.chunksNumber - 1:
                    chunkSize = file.lastChunkSize
                else:
                    chunkSize = file.chunksSize

                if file.status == "S":
                    """peer has the whole file -> open and send it"""

                    try:
                        # file.fileLock.acquire()
                        f = open(file.filepath, 'rb')
                        offset = chunkID * file.chunksSize
                        f.seek(offset)

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING IT"
                            transmission.mySend(thread.client_sock, answer)
                            transmission.sendChunk(thread.client_sock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                        # file.fileLock.release()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
                        # file.fileLock.release()

                if file.status == "D":
                    """peer is still downloading the file -> send chunk from tmp file"""

                    try:
                        # file.fileLock.acquire()

                        chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)

                        f = open(chunkPath, 'rb')

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING IT"
                            transmission.mySend(thread.client_sock, answer)
                            transmission.sendChunk(thread.client_sock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                        # file.fileLock.release()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
                        # file.fileLock.release()
            else:
                answer = "ERROR - UNAVAILABLE CHUNK"
        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED KEY {}".format(key)

    if error:
        # send error answer
        transmission.mySend(thread.client_sock, answer)


def downloadFile(file):
    """


    :param file:
    :return:
    """

    print("Starting synchronization of", file.filename)

    key = file.groupName + "_" + file.filename

    file.syncLock.acquire()

    file.initDownload()

    unavailable = 0
    threshold = 0.7

    tmpDirPath = getTmpDirPath(file)

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

        # chunks_peers is a dictionary where key is the chunkID and
        # value is the list of peer which have that chunk
        chunks_peers = dict()

        # chunksCounter is a dictionary where key is the chunkID and
        # value is the number of peers having that chunk
        chunksCounter = dict()

        for peer in activePeers:
            # ask each peer which chunks it has and collect informations
            # in order to apply the rarest-first approach

            chunksList = getChunksList(file, peer["peerIP"], peer["peerPort"])

            if chunksList is not None:

                # clean the list from already available chunks
                for chunk in file.availableChunks:
                    if chunk in chunksList:
                        chunksList.remove(chunk)

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

        for chunk in sorted(chunksCounter, key=chunksCounter.get):

            # if the number of missing chunks plus the number of already assigned chunks
            # is smaller of half the total number of chunks:
            #       generate a value between 0 and 1 and compare with threshold
            #       if the random value is bigger discard the current chunk
            if len(file.missingChunks) + chunksReady > file.chunksNumber / 2 and random() > threshold:
                # discard this chunk
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

            t = Thread(target=getChunks, args=(file, threadChunksList, peerIP, peerPort, tmpDirPath))
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

    if mergeChunks(file, tmpDirPath):
        # if mergeChunks succeeds clean the download current state
        file.status = "S"
        file.iHaveIt()
        st = os.stat(file.filepath)
        print(st[stat.ST_MTIME])
        file.previousChunks = list()
    else:
        # if mergeChunks fails save the download current state
        file.previousChunks = file.availableChunks

    peerCore.syncThreadsLock.acquire()
    del peerCore.syncThreads[key]
    peerCore.syncThreadsLock.release()

    file.syncLock.release()


def getChunksList(file, peerIP, peerPort):
    """


    :param file:
    :param peerIP:
    :param peerPort:
    :return:
    """

    key = file.groupName + "_" + file.filename

    s = peerCore.createSocket(peerIP, peerPort)
    if s is None:
        return None

    try:
        message = "CHUNKS_LIST {} {}".format(key, file.timestamp)
        transmission.mySend(s, message)
        data = transmission.myRecv(s)
        peerCore.closeSocket(s)
    except (socket.timeout, RuntimeError):
        print("Error while getting chunks list")
        peerCore.closeSocket(s)
        return None

    if str(data).split()[0] == "ERROR":
        print('Received from the peer :', data)
        return None
    else:
        chunksList = eval(str(data))
        return chunksList


def getChunks(file, chunksList, peerIP, peerPort, tmpDirPath):
    """

    :param file:
    :param chunksList:
    :param peerIP:
    :param peerPort:
    :param tmpDirPath:
    :return:
    """

    print(chunksList)

    s = peerCore.createSocket(peerIP, peerPort)
    if s is None:
        return

    for chunkID in chunksList:

        key = file.groupName + "_" + file.filename

        if chunkID == file.chunksNumber - 1:
            chunkSize = file.lastChunkSize
        else:
            chunkSize = file.chunksSize

        try:
            message = "CHUNK {} {} {}".format(key, file.timestamp, chunkID)
            transmission.mySend(s, message)
            answer = transmission.myRecv(s)
        except (socket.timeout, RuntimeError):
            print("Error receiving chunk {}".format(chunkID))
            continue

        if answer.split(" ")[0] == "ERROR":
            continue

        try:
            data = transmission.recvChunk(s, chunkSize)
        except (socket.timeout, RuntimeError):
            print("Error receiving chunk {}".format(chunkID))
            continue

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
            continue

    peerCore.closeSocket(s)


def mergeChunks(file, tmpDirPath):
    """

    :param file:
    :param tmpDirPath:
    :return: boolean
    """

    newFilePath = getNewFilePath(file)

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
    return True


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

    # split filepath into directoryPath and filename
    (dirPath, filename) = os.path.split(file.filepath)
    # remove extension from the filename (if any)
    # WoE stands for Without Extension
    splitFilename = filename.split(".")
    filenameWoE = splitFilename[0]

    # directory path where the chunks have been stored
    tmpDirPath = dirPath + "/" + filenameWoE + "_tmp/"

    return tmpDirPath
