"""This code handles file-sharing operations in myP2PSync peers.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import os
import shutil
import socket
import sys
import time
from random import randint, random
from threading import Thread

import peerCore
import syncScheduler
from fileManagement import CHUNK_SIZE

if "networking" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import shared.networking as networking

MAX_UNAVAILABLE = 5

MAX_THREADS = 5
MAX_CHUNKS_PER_THREAD = 20


def sendChunksList(message, thread):
    messageFields = message.split()
    groupName = messageFields[1]
    fileTreePath = messageFields[2]
    timestamp = int(messageFields[3])

    fileNode = peerCore.localFileTree.getGroup(groupName).findNode(fileTreePath)

    if fileNode is not None:
        if fileNode.file.timestamp == timestamp:
            if fileNode.file.availableChunks is not None:
                if len(fileNode.file.availableChunks) != 0:
                    answer = str(fileNode.file.availableChunks)
                else:
                    answer = "ERROR - EMPTY LIST"
            else:
                answer = "ERROR - NONE LIST"
        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED FILE {} IN GROUP {}".format(fileTreePath, groupName)

    try:
        networking.mySend(thread.clientSock, answer)
    except (socket.timeout, RuntimeError):
        return


def sendChunk(message, thread):
    messageFields = message.split()
    groupName = messageFields[1]
    fileTreePath = messageFields[2]
    timestamp = int(messageFields[3])
    chunkID = int(messageFields[4])

    error = True

    fileNode = peerCore.localFileTree.getGroup(groupName).findNode(fileTreePath)

    if fileNode is not None:
        file = fileNode.file
        if file.timestamp == timestamp:
            if chunkID in file.availableChunks:

                if chunkID == file.chunksNumber - 1:
                    chunkSize = file.lastChunkSize
                else:
                    chunkSize = CHUNK_SIZE

                if file.status == "S":
                    # peer has the whole file -> open and send it

                    try:
                        f = open(file.filepath, 'rb')
                        offset = chunkID * CHUNK_SIZE
                        f.seek(offset)

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING IT"
                            networking.mySend(thread.clientSock, answer)
                            networking.sendChunk(thread.clientSock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"

                if file.status == "D":
                    # peer is still downloading the file -> send chunk from tmp file

                    try:
                        chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)

                        f = open(chunkPath, 'rb')

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING IT"
                            networking.mySend(thread.clientSock, answer)
                            networking.sendChunk(thread.clientSock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"
            else:
                answer = "ERROR - UNAVAILABLE CHUNK"
        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED FILE {} IN GROUP {}".format(fileTreePath, groupName)

    if error:
        # send error answer
        networking.mySend(thread.clientSock, answer)


def checkStatus(key, file):
    """
    This function periodically check the status of the synchronization thread in order to
    detect stop request (for example after a peer in the group removes the file,
    or simply when the synchornization fails after MAX_UNAVAILABLE tries)
    When a stop request is detected the status of the download is saved.
    :param key:
    :param file:
    :return:
    """
    # time between two consecutive checks
    PERIOD = 1

    file.syncLock.acquire()
    file.stopSync = False
    while True:
        # check thread status
        state = syncScheduler.getThreadState(key)
        if state == syncScheduler.SYNC_RUNNING:
            time.sleep(PERIOD)
        else:
            # notify possible other threads
            file.stopSync = True
            if state == syncScheduler.SYNC_SUCCESS:
                # download successfully finished
                # clean the download current state
                file.previousChunks = list()
            elif state == syncScheduler.SYNC_FAILED:
                # save download status
                file.previousChunks = file.availableChunks
            elif state == syncScheduler.FILE_REMOVED:
                # wait for other threads termination (if any)
                time.sleep(1)
                del file
            elif state == syncScheduler.FILE_UPDATED:
                # wait for other threads termination (if any)
                time.sleep(1)
            elif state == syncScheduler.UNDEFINED_STATE:
                pass
            break
    syncScheduler.removeSyncThread(key)
    file.syncLock.release()


def downloadFile(file, taskTimestamp):


    file.syncLock.acquire()
    # this check allows to avoid a race condition like the following:
    # thread1 receive update file and append the task
    # scheduler launch the task
    # meanwhile thread2 update again file stat and append another task
    # without erasing the first one that is already launched
    # at this point file.timestamp refers to the new timestamp so it's
    # different from taskTimestamp: in this case quit the download
    # the last version will be download as soon as the scheduler
    # will select the last inserted task addressing the file
    if taskTimestamp != file.timestamp:
        file.syncLock.release()
        return

    print("Starting synchronization of", file.filename)
    key = file.groupName + "_" + file.treePath

    file.initDownload()

    file.syncLock.release()

    checkThread = Thread(target=checkStatus, args=(key,file))
    checkThread.daemon = True
    checkThread.start()

    unavailable = 0
    tmpDirPath = getTmpDirPath(file)

    # ask for the missing peers while the missing list is not empty
    while len(file.missingChunks) > 0 and unavailable < MAX_UNAVAILABLE:

        if file.stopSync:
            unavailable = MAX_UNAVAILABLE
            break

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

            chunksList = getChunksList(file, peer["address"])

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

        if file.chunksNumber <= numThreads * MAX_CHUNKS_PER_THREAD:
            # don't use random discard
            threshold = 1
        else:
            # use random discard
            threshold = 0.7

        if file.stopSync:
            unavailable = MAX_UNAVAILABLE
            break

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

        if file.stopSync:
            unavailable = MAX_UNAVAILABLE
            break

        threads = list()

        # start threads
        for i in range(0, busyThreads):
            threadChunksList = threadInfo[i]["chunksList"]
            peerPublicAddr = threadInfo[i]["peer"]["address"]

            t = Thread(target=getChunks, args=(file, threadChunksList, peerPublicAddr, tmpDirPath))
            threads.append(t)
            t.start()

        # wait for threads termination
        for i in range(0, busyThreads):
            threads[i].join()

        threshold += 0.1

        file.setProgress()

    if unavailable == MAX_UNAVAILABLE:
        # save download current state in order to restart it at next sync
        print("Synchronization of {} failed or stopped".format(file.filename))
        # re-append task: if the group is no longer active or the file has been removed
        # the scheduler will detect it and it will skip the append operation
        state = syncScheduler.getThreadState(key)
        if state != syncScheduler.FILE_REMOVED and state != syncScheduler.FILE_UPDATED:
            reloadTask = syncScheduler.syncTask(file.groupName, file.treePath, file.timestamp)
            syncScheduler.appendTask(reloadTask, True)
        exitStatus = syncScheduler.SYNC_FAILED

    else:
        # all chunks have been collected
        if mergeChunks(file, tmpDirPath):
            file.status = "S"
            # force OS file timestamp to be file.timestamp
            os.utime(file.filepath, (file.timestamp, file.timestamp))
            file.iHaveIt()
            print("Synchronization of {} successfully terminated".format(file.filename))
            exitStatus = syncScheduler.SYNC_SUCCESS
        else:
            # merge fails
            exitStatus = syncScheduler.SYNC_FAILED

    # this will terminate checkThread
    syncScheduler.stopSyncThreadIfRunning(key, exitStatus)


def getChunksList(file, peerAddr):


    s = networking.createConnection(peerAddr)
    if s is None:
        return None

    try:
        message = str(peerCore.peerID) + " " + \
                  "CHUNKS_LIST {} {} {}".format(file.groupName, file.treePath, file.timestamp)
        networking.mySend(s, message)
        data = networking.myRecv(s)
        networking.closeConnection(s, peerCore.peerID)
    except (socket.timeout, RuntimeError):
        print("Error while getting chunks list")
        networking.closeConnection(s, peerCore.peerID)
        return None

    if str(data).split()[0] == "ERROR":
        print('Received from the peer :', data)
        return None
    else:
        chunksList = eval(str(data))
        return chunksList


def getChunks(file, chunksList, peerAddr, tmpDirPath):


    s = networking.createConnection(peerAddr)
    if s is None:
        return

    for chunkID in chunksList:

        if file.stopSync:
            break

        if chunkID == file.chunksNumber - 1:
            chunkSize = file.lastChunkSize
        else:
            chunkSize = CHUNK_SIZE

        try:
            message = str(peerCore.peerID) + " " + \
                      "CHUNK {} {} {} {}".format(file.groupName, file.treePath, file.timestamp, chunkID)
            networking.mySend(s, message)
            answer = networking.myRecv(s)
        except (socket.timeout, RuntimeError):
            print("Error receiving chunk {}".format(chunkID))
            continue

        if answer.split(" ")[0] == "ERROR":
            continue

        try:
            data = networking.recvChunk(s, chunkSize)
        except (socket.timeout, RuntimeError):
            print("Error receiving chunk {}".format(chunkID))
            continue

        try:
            peerCore.pathCreationLock.acquire()
            if not os.path.exists(tmpDirPath):
                print("Creating the path: " + tmpDirPath)
                os.makedirs(tmpDirPath)
            peerCore.pathCreationLock.release()

            chunkPath = tmpDirPath + "chunk" + str(chunkID)

            f = open(chunkPath, 'wb')

            f.write(data)

            f.close()

            file.missingChunks.remove(chunkID)
            file.availableChunks.append(chunkID)

        except FileNotFoundError:
            continue

    networking.closeConnection(s, peerCore.peerID)


def mergeChunks(file, tmpDirPath):
    """

    :param file:
    :param tmpDirPath:
    :return: boolean
    """

    newFilePath = getNewFilePath(file)

    # merge chunks writing each chunks in the new file
    try:

        dirPath, __ = os.path.split(newFilePath)
        peerCore.pathCreationLock.acquire()
        if not os.path.exists(dirPath):
            print("Creating the path: " + dirPath)
            os.makedirs(dirPath)
        peerCore.pathCreationLock.release()

        f1 = open(newFilePath, 'wb')
        if file.filesize > 0:
            for chunkID in range(0, file.chunksNumber):
                chunkPath = tmpDirPath + "chunk" + str(chunkID)
                with open(chunkPath, 'rb') as f2:
                    f1.write(f2.read())
        f1.close()
    except FileNotFoundError:
        print("Error while creating the new file")
        return False

    # remove previous version of the file (if any)
    if os.path.exists(file.filepath):
        os.remove(file.filepath)

    os.rename(newFilePath, file.filepath)

    # remove chunks directory
    if file.filesize > 0:
        shutil.rmtree(tmpDirPath)

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
