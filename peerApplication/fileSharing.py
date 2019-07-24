"""
Project: myP2PSync
This code handles file-sharing operations (upload, download) in myP2PSync peers.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""

import hashlib
import math
import os
import shutil
import socket
import sys
import time
from random import random, shuffle
from threading import Thread, Lock

import peerCore
import syncScheduler
from fileManagement import CHUNK_SIZE

if "networking" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import shared.networking as networking


# define the period of time between 2 consecutive refreshes of the chunksList
REFRESH_LIST_PERIOD = 10

# maximum number of attempts before quitting a synchronization
MAX_UNAVAILABLE = 5

# maximum number of peers from which chunks list can be retrieved
# in a single iteration of the download protocol, eventual peers not
# considered cannot be used to retrieve chunks too
MAX_PEERS = 10

# parameters used to download the file
MAX_THREADS = 5
MAX_CHUNKS = 70

# time between two consecutive checks on the synchronization thread status
CHECK_PERIOD = 1.0

# parameters for chunks random discard
INITIAL_TRESHOLD = 0.5
TRESHOLD_INC_STEP = 0
COMPLETION_RATE = 0.95

# maximum number of getChunk request leading to an error allowed before to quit a connection
MAX_ERRORS = 3


def sendChunksList(message, thread):
    """
    Sends local chunks list of a file to another peer that requests it.
    :param message: message received
    :param thread: thread handler of the connection
    :return: void
    """

    # get message parameters
    messageFields = message.split()
    groupName = messageFields[1]
    fileTreePath = messageFields[2]
    timestamp = int(messageFields[3])

    # retrieve file information
    fileNode = peerCore.localFileTree.getGroup(groupName).findNode(fileTreePath)

    if fileNode is not None:
        if fileNode.file.timestamp == timestamp:
            if fileNode.file.availableChunks is not None:
                if len(fileNode.file.availableChunks) != 0:

                    # send back chunks list
                    answer = str(fileNode.file.availableChunks)

                else:
                    answer = "ERROR - EMPTY LIST"
            else:
                answer = "ERROR - UNITIALIZED LIST"
        else:
            answer = "ERROR - DIFFERENT VERSION"
    else:
        answer = "ERROR - UNRECOGNIZED FILE {} IN GROUP {}".format(fileTreePath, groupName)

    try:
        networking.mySend(thread.clientSock, answer)
    except (socket.timeout, RuntimeError, ValueError):
        print("Error while sending: ", answer)


def sendChunk(message, thread):
    """
    Send request chunk to another peer.
    :param message: message received
    :param thread: thread handler of the connection
    :return: void
    """

    # get message parameters
    messageFields = message.split()
    groupName = messageFields[1]
    fileTreePath = messageFields[2]
    timestamp = int(messageFields[3])
    chunkID = int(messageFields[4])

    error = True

    # get local file information
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
                    """peer has the whole file -> open and send it"""

                    try:
                        f = open(file.filepath, 'rb')
                        offset = chunkID * CHUNK_SIZE
                        f.seek(offset)

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - {}".format(hashlib.md5(dataChunk).hexdigest())
                            networking.mySend(thread.clientSock, answer)
                            networking.sendChunk(thread.clientSock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"

                if file.status == "D":
                    """peer is still downloading the file -> send chunk from tmp file"""

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
        # send error answer: other peer will not wait for the chunk
        try:
            networking.mySend(thread.clientSock, answer)
        except (socket.timeout, RuntimeError, ValueError):
            print("Error while sending: ", answer)


def startFileSync(file, taskTimestamp):
    """
    Main thread for the synchronization of a file.
    It starts the download and check periodically the status of the sync
    in order to intercept external interruption.
    :param file: File object
    :param taskTimestamp: timestamp value of the synchronization
    :return: void
    """

    # acquire lock on the file
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

    file.stopSync = False

    # start download thread
    t = Thread(target=downloadFile, args=(file, key))
    t.daemon = True
    t.start()

    while True:
        # check thread status
        state = syncScheduler.getThreadState(key)

        if state == syncScheduler.SYNC_RUNNING:
            time.sleep(CHECK_PERIOD)

        else:
            # notify possible other threads
            file.stopSync = True

            if state == syncScheduler.SYNC_SUCCESS:
                # download successfully finished
                # clean the download current state
                file.previousChunks = list()

            elif state == syncScheduler.SYNC_FAILED or \
                    state == syncScheduler.SYNC_STOPPED:
                # save download status
                file.previousChunks = file.availableChunks

            elif state == syncScheduler.FILE_REMOVED:
                # wait for other threads termination (if any)
                time.sleep(1)
                del file
                syncScheduler.removeSyncThread(key)
                return

            elif state == syncScheduler.FILE_UPDATED:
                # wait for other threads termination (if any)
                time.sleep(1)

            elif state == syncScheduler.UNDEFINED_STATE:
                pass

            break
    syncScheduler.removeSyncThread(key)

    # release file lock -> can trigger new synchronization on the same file
    # or modification on the file parameters
    file.syncLock.release()


class Download:

    def __init__(self):
        self.rarestFirstChunksList = None
        self.scheduledChunks = None
        self.chunksToPeers = None
        self.activePeers = None
        self.complete = False
        self.unavailable = False
        self.lock = Lock()


def downloadFile(file, key):

    # initialize download parameters e.g. chunksNumber and chunks list
    file.initSync()

    unavailable = False
    tmpDirPath = getTmpDirPath(file)
    activeThreads = 0

    if file.filesize == 0:
        # all chunks have been collected
        mergeChunks(file, tmpDirPath)
        file.status = "S"
        # force OS file timestamp to be file.timestamp
        os.utime(file.filepath, (file.timestamp, file.timestamp))
        file.initSeed()
        exitStatus = syncSuccess(file, 0)
    else:

        dl = Download()

        chunksSchedulerThread = Thread(target = chunksScheduler, args=(dl,file))
        chunksSchedulerThread.daemon = True
        chunksSchedulerThread.start()

        while dl.activePeers is None:
            time.sleep(0.1)
            if dl.unavailable or file.stopSync:
                unavailable = True
                break

        if not unavailable:

            activePeers = dl.activePeers

            for peer in activePeers:
                getChunksThread = Thread(target = getChunks, args = (dl, file, peer, tmpDirPath))
                getChunksThread.daemon = True
                getChunksThread.start()
                activeThreads += 1

            # get download start time
            startTime = time.time()

            while not dl.complete:
                for peer in dl.activePeers:
                    if peer not in activePeers and activeThreads < MAX_THREADS:
                        getChunksThread = Thread(target=getChunks, args=(dl, file, peer, tmpDirPath))
                        getChunksThread.daemon = True
                        getChunksThread.start()
                        activeThreads += 1
                for peerID in activePeers:
                    if peerID not in dl.activePeers:
                        activeThreads -= 1
                if dl.unavailable or file.stopSync:
                    unavailable = True
                    break

                activePeers = dl.activePeers
                time.sleep(1)

            if not unavailable:
                # get end download time
                endTime = time.time()

                # all chunks have been collected
                mergeChunks(file, tmpDirPath)
                file.status = "S"
                # force OS file timestamp to be file.timestamp
                os.utime(file.filepath, (file.timestamp, file.timestamp))
                file.initSeed()
                exitStatus = syncSuccess(file, math.floor(endTime - startTime))
            else:
                exitStatus = syncFail(file, key)
        else:
            exitStatus = syncFail(file, key)


    # this will terminate checkThread
    syncScheduler.stopSyncThreadIfRunning(key, exitStatus)


def syncSuccess(file, syncTime):
    print("Synchronization of {} successfully terminated".format(file.filename))
    print("Synchronization completed in {} seconds".format(syncTime))
    return syncScheduler.SYNC_SUCCESS


def syncFail(file, key):
    # save download current state in order to restart it at next sync
    print("Synchronization of {} failed or stopped".format(file.filename))
    # re-append task: if the group is no longer active or the file has been removed
    # the scheduler will detect it and it will skip the append operation
    state = syncScheduler.getThreadState(key)
    if state != syncScheduler.FILE_REMOVED and state != syncScheduler.FILE_UPDATED:
        reloadTask = syncScheduler.syncTask(file.groupName, file.treePath, file.timestamp)
        syncScheduler.appendTask(reloadTask, True)
    return syncScheduler.SYNC_FAILED


def chunksScheduler(dl, file):

    unavailable = 0
    dl.rarestFirstChunksList = set()
    dl.scheduledChunks = set()
    dl.chunksToPeers = dict()

    while len(file.missingChunks) > 0 and unavailable < MAX_UNAVAILABLE:

        # check synchronization status
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
            # empty list retrieved: no active peers for that group
            unavailable += 1
            time.sleep(1)
            continue

        # chunksToPeers is a dictionary where key is the chunkID and
        # value is the list of peer which have that chunk
        chunksToPeers = dict()

        # chunksCounter is a dictionary where key is the chunkID and
        # value is the number of peers having that chunk
        chunksCounter = dict()

        j = 0

        # random.shuffle() guarantees that when the number of active peers
        # is bigger than MAX_PEERS different peers are selected in different iterations
        shuffle(activePeers)

        # ask each peer which chunks it has and collect informations
        # in order to apply the rarest-first approach
        for peer in activePeers:

            # limits the number of peers considered
            if j == MAX_PEERS:
                break

            chunksList = getChunksList(file, peer["address"])

            if chunksList is not None:

                j += 1

                # clean the list from already retrieved chunks
                chunksList = [chunk for chunk in chunksList if chunk in file.missingChunks]

                # fill chunk_peers and chunksCounter
                for chunk in chunksList:
                    if chunk in chunksCounter:
                        chunksCounter[chunk] += 1
                        chunksToPeers[chunk].append(peer)
                    else:
                        chunksCounter[chunk] = 1
                        chunksToPeers[chunk] = list()
                        chunksToPeers[chunk].append(peer)

        if len(chunksCounter) == 0:
            # active peers don't have missing chunks
            unavailable += 1
            time.sleep(1)
            continue

        dl.lock.acquire()

        for chunk in sorted(chunksCounter, key=chunksCounter.get):
            if chunk not in dl.scheduledChunks:
                dl.rarestFirstChunksList.add(chunk)
            dl.chunksToPeers[chunk] = chunksToPeers[chunk]
        dl.activePeers = activePeers

        dl.lock.release()

        for i in range(0, REFRESH_LIST_PERIOD):
            if file.stopSync:
                unavailable = MAX_UNAVAILABLE
                break
            if len(file.missingChunks) == 0:
                break
            else:
                file.setProgress()
                time.sleep(1)

    if unavailable == MAX_UNAVAILABLE:
        dl.unavailable = True
    else:
        dl.complete = True



def getChunksList(file, peerAddr):
    """
    Retrives the chunks list for a file from another active peer.
    :param file: File object
    :param peerAddr: IP address and port of the destination peer
    :return: chunksList (list() of integer, each one represents a chunkID)
    """

    # connect to remote peer
    s = networking.createConnection(peerAddr)
    if s is None:
        return None

    try:
        # send request and get the answer
        message = str(peerCore.peerID) + " " + \
                  "CHUNKS_LIST {} {} {}".format(file.groupName, file.treePath, file.timestamp)
        networking.mySend(s, message)
        data = networking.myRecv(s)
        networking.closeConnection(s, peerCore.peerID)
    except (socket.timeout, RuntimeError, ValueError):
        print("Error while getting chunks list")
        networking.closeConnection(s, peerCore.peerID)
        return None

    if str(data).split()[0] == "ERROR":
        # remote peer answered with an error string
        print('Received from the peer :', data)
        return None
    else:
        # success: return chunksList
        chunksList = eval(str(data))
        return chunksList


def getChunks(dl, file, peer, tmpDirPath):

    peerAddr = peer["address"]

    if len(file.availableChunks) + len(dl.scheduledChunks) >= COMPLETION_RATE * file.chunksNumber\
            or len(file.missingChunks) <= MAX_CHUNKS:
        # don't use random discard
        threshold = 1

    else:
        # use random discard
        threshold = INITIAL_TRESHOLD

    # connect to remote peer
    s = networking.createConnection(peerAddr)
    if s is None:
        return

    while not dl.complete:

        if file.stopSync:
            break

        chunksList = list()

        dl.lock.acquire()

        for chunk in dl.rarestFirstChunksList:
            if len(chunksList) >= MAX_CHUNKS:
                break
            if len(file.missingChunks) > MAX_CHUNKS \
                    and len(file.availableChunks) + len(dl.scheduledChunks) <= COMPLETION_RATE * file.chunksNumber\
                    and random() > threshold:
                # discard this chunk
                continue
            if peer in dl.chunksToPeers[chunk]:
                chunksList.append(chunk)
                dl.scheduledChunks.add(chunk)

        for chunk in chunksList:
            dl.rarestFirstChunksList.remove(chunk)

        dl.lock.release()

        # decrease discard probability for next round
        threshold += TRESHOLD_INC_STEP

        if len(chunksList) == 0:

            for i in range(0, 5):
                if file.stopSync or dl.complete:
                    break
                else:
                    time.sleep(1)

        else:

            errors = 0

            for i in range(0, len(chunksList)):

                chunkID = chunksList[i]

                if errors == MAX_ERRORS:
                    networking.closeConnection(s, peerCore.peerID)
                    # try to re-establish connection
                    s = networking.createConnection(peerAddr)
                    if s is None:
                        # connection broken or peer disconnected
                        for j in range(i, len(chunksList)):
                            chunk = chunksList[j]
                            errorOnGetChunk(dl, chunk)
                        return


                # check eventual stop forced from main thread
                if file.stopSync:
                    break

                try:
                    # send request and wait for a string response
                    message = str(peerCore.peerID) + " " + \
                              "CHUNK {} {} {} {}".format(file.groupName, file.treePath, file.timestamp, chunkID)
                    networking.mySend(s, message)
                    answer = networking.myRecv(s)
                except (socket.timeout, RuntimeError, ValueError):
                    print("Error receiving message about chunk {}".format(chunkID))
                    errorOnGetChunk(dl, chunkID)
                    errors += 1
                    continue

                if answer.split()[0] == "ERROR":
                    # error: consider next chunks
                    print("Received:", answer)
                    errorOnGetChunk(dl, chunkID)
                    continue

                try:
                    # success: get the chunk

                    # evaluate chunks size
                    if chunkID == file.chunksNumber - 1:
                        chunkSize = file.lastChunkSize
                    else:
                        chunkSize = CHUNK_SIZE

                    data = networking.recvChunk(s, chunkSize)
                except (socket.timeout, RuntimeError):
                    print("Error receiving chunk {}".format(chunkID))
                    errorOnGetChunk(dl, chunkID)
                    errors += 1
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

                    try:
                        file.missingChunks.remove(chunkID)
                        file.availableChunks.append(chunkID)
                        dl.scheduledChunks.remove(chunkID)
                    except ValueError:
                        pass

                except FileNotFoundError:
                    errorOnGetChunk(dl, chunkID)
                    continue

    networking.closeConnection(s, peerCore.peerID)


def errorOnGetChunk(dl, chunkID):
    dl.lock.acquire()
    dl.rarestFirstChunksList.add(chunkID)
    dl.scheduledChunks.remove(chunkID)
    dl.lock.release()

def mergeChunks(file, tmpDirPath):
    """
    :param file:
    :param tmpDirPath:
    :return: boolean
    """

    newFilePath = getNewFilePath(file)

    # save available chunks in case the merge operations fails or it's stopped
    file.previousChunks = file.availableChunks

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
    :return: newFilePath
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
    Build the new temporary directory path
               ex.
               file.filepath = home/prova.txt
               dirPath = home/
               tmpDirPath = home/prova.txt_tmp/
    :param file: File object
    :return: string representing the path
    """

    # split filepath into directoryPath and filename
    (dirPath, filename) = os.path.split(file.filepath)

    # directory path where the chunks have been stored
    tmpDirPath = dirPath + "/" + filename + "_tmp/"

    return tmpDirPath