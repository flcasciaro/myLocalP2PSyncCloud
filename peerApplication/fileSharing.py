"""
Project: myP2PSync
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC

This code handles file-sharing operations (upload, download) in myP2PSync peers.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.
"""

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


# define the period of time between 2 consecutive refreshes of the rarestFirstChunksList
REFRESH_LIST_PERIOD = 10

# maximum number of attempts before quitting a synchronization
MAX_UNAVAILABLE = 5

# maximum number of peers from which chunks list can be retrieved
# in a single iteration of the download protocol, eventual peers not
# considered cannot be used to retrieve chunks too
MAX_PEERS = 10

# parameters used to download the file
# maximum number of parallel threads getting chunks
MAX_THREADS = 5
# maximum number of chunks that can be asked by a getChunk thread in a single iteration
# of its internal cycle: it's not unbounded in order to don't block other threads, it's not
# a small value in order to avoid too much cycle
MAX_CHUNKS = 100

# time between two consecutive checks on the synchronization thread status
CHECK_PERIOD = 1.0

# parameters for chunks random discard
INITIAL_TRESHOLD = 0.5          # discard (INITIAL_TRESHOLD*100)% of the chunks
TRESHOLD_INC_STEP = 0           # increment of the treshold after each iteration
COMPLETION_RATE = 0.95          # realize random discard until (COMPLETION_RATE*100)% of the file is downloaded

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
        # check timestamp in order to ensure local file validity
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
    Send requested chunk to another peer.
    :param message: message received
    :param thread: thread handler of the connection
    :return: void
    """

    # get message parameters
    messageFields = message.split()
    groupName = messageFields[1]
    fileTreePath = messageFields[2]
    timestamp = int(messageFields[3])

    # id of the requested chunk
    chunkID = int(messageFields[4])

    error = True

    # get local file information
    fileNode = peerCore.localFileTree.getGroup(groupName).findNode(fileTreePath)

    if fileNode is not None:

        file = fileNode.file

        # check timestamp in order to ensure local file validity
        if file.timestamp == timestamp:
            if chunkID in file.availableChunks:

                # get chunk's size
                if chunkID == file.chunksNumber - 1:
                    chunkSize = file.lastChunkSize
                else:
                    chunkSize = CHUNK_SIZE

                if file.status == "S":
                    # peer has the whole file: open and send it

                    try:
                        f = open(file.filepath, 'rb')
                        offset = chunkID * CHUNK_SIZE
                        f.seek(offset)

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING THE CHUNK"
                            networking.mySend(thread.clientSock, answer)
                            networking.sendChunk(thread.clientSock, dataChunk, chunkSize)
                        except (socket.timeout, RuntimeError):
                            print("Error while sending chunk {}".format(chunkID))

                        f.close()
                    except FileNotFoundError:
                        answer = "ERROR - IT WAS NOT POSSIBLE TO OPEN THE FILE"

                if file.status == "D":
                    # peer is still downloading the file -> send chunk from tmp directory

                    try:
                        chunkPath = file.filepath + "_tmp/" + "chunk" + str(chunkID)

                        f = open(chunkPath, 'rb')

                        dataChunk = f.read(chunkSize)

                        try:
                            error = False
                            answer = "OK - I'M SENDING THE CHUNK"
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
    """
    Data structure useful to collect download information.
    """

    def __init__(self):
        self.rarestFirstChunksList = None               # list of missing chunks ordered by their rarity
        self.scheduledChunks = None                     # list of chunks already scheduled by a getChunks
                                                        # thread in order to get them
        self.chunksToPeers = None                       # mapping chunkID -> list of active peers that have that chunk
        self.activePeers = None                         # list of active peers
        self.complete = False                           # download complete
        self.unavailable = False                        # file unavailable
        self.lock = Lock()                              # lock on the data structure


def downloadFile(file, key):
    """
    This function manages the creation of all the threads related to a file download.
    It creates the chunksManager thread and the getChunks threads.
    :param file: File object
    :param key: File key (groupName_filename)
    :return: void
    """

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

        # create and start chunksManager thread, it collect chunks list from other active peers
        # and calculate the missing chunks rarestFirstChunksList
        chunksManagerThread = Thread(target = chunksManager, args=(dl,file))
        chunksManagerThread.daemon = True
        chunksManagerThread.start()

        # wait for the completion of the first iteration of chunksManager
        while dl.activePeers is None:
            time.sleep(0.1)
            if dl.unavailable or file.stopSync:
                unavailable = True
                break

        if not unavailable:

            activePeers = dl.activePeers

            for peer in activePeers:
                # create a getChunks thread for each active peers
                if activeThreads == MAX_THREADS:
                    break
                getChunksThread = Thread(target = getChunks, args = (dl, file, peer, tmpDirPath))
                getChunksThread.daemon = True
                getChunksThread.start()
                activeThreads += 1

            # get download start time
            startTime = time.time()

            # while the download is not complete
            while not dl.complete:
                # create new getChunks thread if new peers are active
                for peer in dl.activePeers:
                    if peer not in activePeers and activeThreads < MAX_THREADS:
                        getChunksThread = Thread(target=getChunks, args=(dl, file, peer, tmpDirPath))
                        getChunksThread.daemon = True
                        getChunksThread.start()
                        activeThreads += 1
                # detect new unactive peers
                for peerID in activePeers:
                    if peerID not in dl.activePeers:
                        activeThreads -= 1

                # check download stop conditions
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
    """
    Synchronization ended successfully. Print success messages.
    :param file: File object
    :param syncTime: indicate the time between syncStart and syncEnd
    :return: syncScheduler status
    """
    print("Synchronization of {} successfully terminated".format(file.filename))
    print("Synchronization completed in {} seconds".format(syncTime))
    return syncScheduler.SYNC_SUCCESS


def syncFail(file, key):
    """
    Synchronization fails. Print error messages and reload sync task.
    :param file: File object
    :param key: File key (groupName_filename)
    :return: syncScheduler status
    """
    # save download current state in order to restart it at next sync
    print("Synchronization of {} failed or stopped".format(file.filename))
    # re-append task: if the group is no longer active or the file has been removed
    # the scheduler will detect it and it will skip the append operation
    state = syncScheduler.getThreadState(key)
    if state != syncScheduler.FILE_REMOVED and state != syncScheduler.FILE_UPDATED:
        reloadTask = syncScheduler.syncTask(file.groupName, file.treePath, file.timestamp)
        syncScheduler.appendTask(reloadTask, True)
    return syncScheduler.SYNC_FAILED


def chunksManager(dl, file):
    """
    Periodically asks other active peers for their chunksList of file.
    Then, it calculates the rarestFirstChunksList of missing chunks.
    :param dl: Download object, contains download information
    :param file: File object
    :return: void
    """

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
            # error occurred while asking the peers list to the tracker
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

            # limits to a maximum MAX_PEERS the number of peers considered
            if j == MAX_PEERS:
                break

            # ask the peer for its chunksList for the file
            chunksList = getChunksList(file, peer["address"])

            if chunksList is not None:

                j += 1

                # clean the list from already retrieved chunks
                chunksList = [chunk for chunk in chunksList if chunk in file.missingChunks]

                # fill chunkToPeers and chunksCounter
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

        # update download information
        for chunk in sorted(chunksCounter, key=chunksCounter.get):
            if chunk not in dl.scheduledChunks:
                dl.rarestFirstChunksList.add(chunk)
            dl.chunksToPeers[chunk] = chunksToPeers[chunk]
        dl.activePeers = activePeers

        dl.lock.release()

        # wait REFRESH_LIST_PERIOD seconds, checking every second
        # for a possible termination of the download or external stop
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
    """
    This function allows to retrieve chunks from another active peer.
    Chunks are selected from the dl.rarestFirstChunksList and requested.
    The function iterate its behavior until the download is complete.
    :param dl: download information and data
    :param file: File object
    :param peer: peer information, it's a dictionary
    :param tmpDirPath: path of the directory where chunk will be stored
    :return: void
    """

    # get peer address
    peerAddr = peer["address"]

    if len(file.availableChunks) + len(dl.scheduledChunks) >= COMPLETION_RATE * file.chunksNumber\
            or len(file.missingChunks) <= MAX_CHUNKS:
        # don't use random discard if the number of missing chunks is smaller than a certain amount
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

        # list of chunks that the function will retrieve in a single iteration
        chunksList = list()

        dl.lock.acquire()

        for chunk in dl.rarestFirstChunksList:
            if len(chunksList) >= MAX_CHUNKS:
                # chunksList full
                break
            if len(file.missingChunks) > MAX_CHUNKS \
                    and len(file.availableChunks) + len(dl.scheduledChunks) <= COMPLETION_RATE * file.chunksNumber\
                    and random() > threshold:
                # randomly discard this chunk from the request list
                continue
            if peer in dl.chunksToPeers[chunk]:
                # add chunk to request list and scheduled list
                chunksList.append(chunk)
                dl.scheduledChunks.add(chunk)

        # remove scheduled chunks from main list
        # this avoid that other threads request scheduled chunks
        for chunk in chunksList:
            dl.rarestFirstChunksList.remove(chunk)

        dl.lock.release()

        # decrease discard probability for next round
        threshold += TRESHOLD_INC_STEP

        if len(chunksList) == 0:
            # if no chunks can be request to the peer
            # sleep 5 seconds and then try again to compute chunksList

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
                            # reload in the main list all the scheduled chunks
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
                        # print("Creating the path: " + tmpDirPath)
                        os.makedirs(tmpDirPath)
                    peerCore.pathCreationLock.release()

                    chunkPath = tmpDirPath + "chunk" + str(chunkID)

                    # write chunk in a new file
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
    """
    Function that handles an error occurred while asking for a certain chunk.
    It makes a specific chunk available to be ask for other getChunks threads.
    :param dl: download information
    :param chunkID: number of the chunk of the file
    :return: void
    """
    dl.lock.acquire()
    # add the chunk to the main list
    dl.rarestFirstChunksList.add(chunkID)
    # remove the chunk from the list of scheduled chunks
    dl.scheduledChunks.remove(chunkID)
    dl.lock.release()


def mergeChunks(file, tmpDirPath):
    """
    This function merges all the chunks of a file in a new file.
    :param file: File object
    :param tmpDirPath: path of the directory where all the chunks have been collected
    :return: boolen value (True for success)
    """

    # path of the new file
    newFilePath = getNewFilePath(file)

    # save available chunks in case the merge operations fails or it's stopped
    file.previousChunks = file.availableChunks

    # merge chunks writing each chunks in the new file
    try:

        dirPath, __ = os.path.split(newFilePath)
        peerCore.pathCreationLock.acquire()
        if not os.path.exists(dirPath):
            # print("Creating the path: " + dirPath)
            os.makedirs(dirPath)
        peerCore.pathCreationLock.release()

        f1 = open(newFilePath, 'wb')
        # merge chunks
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

    # rename the tmp file to the real name of the file
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