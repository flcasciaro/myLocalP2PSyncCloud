"""
Project: myP2PSync
This code handles file-sharing operations (upload, download) in myP2PSync peers.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC
"""

import math
import os
import socket
import sys
import time
from random import randint, random, shuffle
from threading import Thread

import peerCore
import syncScheduler
from fileManagement import CHUNK_SIZE

if "networking" not in sys.modules:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import shared.networking as networking

# maximum number of attempts before quitting a synchronization
MAX_UNAVAILABLE = 5

# maximum number of peers from which chunks list can be retrieved
# in a single iteration of the download protocol, eventual peers not
# considered cannot be used to retrieve chunks too
MAX_PEERS = 10

# parameters used to download the file
MAX_THREADS = 5
MAX_CHUNKS_PER_THREAD = 50

# time between two consecutive checks on the synchronization thread status
CHECK_PERIOD = 1.0

# parameters for chunks random discard
INITIAL_TRESHOLD = 0.5
TRESHOLD_INC_STEP = 0.02

# maximum number of getChunk request leading to an error allowed before to quit a connection
MAX_CONSECUTIVE_ERRORS = 3


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
                    # peer has already the whole file
                    filepath = file.filepath
                else:
                    # file status is 'D'
                    # peer has still the temporary version of the file
                    # where it is collecting chunks
                    filepath = getNewFilePath(file)
                try:
                    f = open(filepath, 'rb')
                    offset = chunkID * CHUNK_SIZE
                    f.seek(offset)

                    dataChunk = f.read(chunkSize)

                    try:
                        error = False
                        # send ok message, trigger recv on the remote peer
                        answer = "OK - I'M SENDING IT"
                        networking.mySend(thread.clientSock, answer)
                        # send chunk
                        networking.sendChunk(thread.clientSock, dataChunk, chunkSize)
                    except (socket.timeout, RuntimeError, ValueError):
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

    # start download thread
    t = Thread(target=downloadFile, args=(file, key))
    t.daemon = True
    t.start()

    file.stopSync = False
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


def downloadFile(file, key):
    """
    This function contains the main algorithm used to retrieve a file in a P2P fashion.
    While there are missing chunks:
        1) asks other active peers for their chunks list
        2) build rarest-first chunks list
        3) assign chunks to different threads, each thread will ask chunks to a single peer
        4) start threads and wait for their termination
    :param file: File object that will be retrieved
    :param key: groupName_treePath string
    :return: void
    """

    # initialize download parameters e.g. chunksNumber and chunks list
    file.initSync()

    unavailable = 0
    newFilePath = getNewFilePath(file)

    # get download start time
    startTime = time.time()

    # ask for the missing chunks while the missing list is not empty
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

        j = 0
        minRTT = None

        # random.shuffle() guarantees that when the number of active peers
        # is bigger than MAX_PEERS different peers are selected in different iterations
        shuffle(activePeers)

        # ask each peer which chunks it has and collect informations
        # in order to apply the rarest-first approach
        for peer in activePeers:

            # limits the number of peers considered
            if j == MAX_PEERS:
                break

            # ask chunks list and record RTT associated to the peer
            startRequest = time.time()
            chunksList = getChunksList(file, peer["address"])
            endRequest = time.time()

            if chunksList is not None:

                j += 1
                peer["RTT"] = endRequest - startRequest
                if minRTT is None:
                    minRTT = peer["RTT"]
                elif peer["RTT"] < minRTT:
                    minRTT = peer["RTT"]

                # clean the list from already available chunks
                for chunk in file.availableChunks:
                    if chunk in chunksList:
                        chunksList.remove(chunk)

                # fill chunk_peers and chunksCounter
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

        # define maximum number of thread that will work in parallel
        # asking chunks to different peers
        if len(activePeers) >= MAX_THREADS:
            numThreads = MAX_THREADS
        else:
            numThreads = len(activePeers) if len(activePeers) < MAX_PEERS else MAX_PEERS

        # for each peers considered before (from which the chunks list
        # has been retrieved) define the maximum number that can be requested
        # according to its RTT
        # furthermore, store the sum of maxChunks into totalIterationChunks
        totalIterationChunks = 0
        for peer in activePeers:
            if "RTT" in peer:
                peer["maxChunks"] = (minRTT / peer["RTT"]) * MAX_CHUNKS_PER_THREAD
                totalIterationChunks += peer["maxChunks"]

        if file.chunksNumber <= totalIterationChunks:
            # don't use random discard
            threshold = 1
        else:
            # use random discard
            threshold = INITIAL_TRESHOLD

        # check synchronization status
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

        # consider all the chunks, rarest first
        for chunk in sorted(chunksCounter, key=chunksCounter.get):

            # if the number of missing chunks minus the number of already assigned chunks
            # is smaller of half the total number of chunks:
            #       generate a value between 0 and 1 and compare with threshold
            #       if the random value is bigger discard the current chunk
            if len(file.missingChunks) - chunksReady > file.chunksNumber / 2 and random() > threshold:
                # discard this chunk
                continue

            if chunksReady == totalIterationChunks:
                # all the chunk lists have been filled completely
                break

            found = False

            # try to insert in one of the previous peer chunks list
            for i in range(0, busyThreads):

                if threadInfo[i]["peer"] is None:
                    # none of the already considered peers can handle this chunk
                    break
                if threadInfo[i]["peer"] in chunks_peers[chunk]:
                    if len(threadInfo[i]["chunksList"]) < threadInfo[i]["peer"]["maxChunks"]:
                        threadInfo[i]["chunksList"].append(chunk)
                        chunksReady += 1
                        found = True
                        break

            if found:
                # chunk scheduled: go to next chunks
                continue

            if busyThreads == numThreads:
                # go to next chunks because no thread is available for the current one
                # and cannot add another thread
                continue

            # choose a random peer from the list
            r = randint(0, len(chunks_peers[chunk]) - 1)
            i = 0

            # iterate over all the peers that have this chunks
            while i <= (len(chunks_peers[chunk]) - 1):

                # randomly select a peer
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
                    # the thread associate to the peer has reached maxChunks size list
                    # because was not possible to select it in the first part of the
                    # scheduling algorithm, consider next peer in the list
                    r = (r + 1) % len(chunks_peers[chunk])
                    i += 1

        # check synchronization status
        if file.stopSync:
            unavailable = MAX_UNAVAILABLE
            break

        threads = list()

        # start threads
        for i in range(0, busyThreads):
            threadChunksList = threadInfo[i]["chunksList"]
            peerAddr = threadInfo[i]["peer"]["address"]

            t = Thread(target=getChunks, args=(file, threadChunksList, peerAddr, newFilePath))
            threads.append(t)
            t.start()

        # wait for threads termination
        for i in range(0, busyThreads):
            threads[i].join()

        # decrease discard probability
        threshold += TRESHOLD_INC_STEP

        file.setProgress()

    # get end download time
    endTime = time.time()

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
        endDownload(file, newFilePath)
        file.status = "S"
        # force OS file timestamp to be file.timestamp
        os.utime(file.filepath, (file.timestamp, file.timestamp))
        file.initSeed()
        print("Synchronization of {} successfully terminated".format(file.filename))
        print("Synchronization completed in {} seconds".format(math.floor(endTime - startTime)))
        exitStatus = syncScheduler.SYNC_SUCCESS

    # this will terminate checkThread
    syncScheduler.stopSyncThreadIfRunning(key, exitStatus)


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


def getChunks(file, chunksList, peerAddr, newFilepath):
    """
    Opens a connection to a remote peer and ask for a list of chunks.
    :param file: File object
    :param chunksList: list of integers representing chunksID
    :param peerAddr: IPaddress and port of the remote peer
    :param newFilepath: temporary path of the file where chunks will be collected
    :return: void
    """

    # connect to remote peer
    s = networking.createConnection(peerAddr)
    if s is None:
        return

    consecutiveErrors = 0

    for chunkID in chunksList:

        # check eventual stop forced from main thread
        if file.stopSync:
            break

        if consecutiveErrors == MAX_CONSECUTIVE_ERRORS:
            break

        # evaluate chunks size
        if chunkID == file.chunksNumber - 1:
            chunkSize = file.lastChunkSize
        else:
            chunkSize = CHUNK_SIZE

        try:
            # send request and wait for a string response
            message = str(peerCore.peerID) + " " + \
                      "CHUNK {} {} {} {}".format(file.groupName, file.treePath, file.timestamp, chunkID)
            networking.mySend(s, message)
            answer = networking.myRecv(s)
        except (socket.timeout, RuntimeError, ValueError):
            consecutiveErrors += 1
            print("Error receiving message about chunk {}".format(chunkID))
            continue

        consecutiveErrors = 0

        if answer.split(" ")[0] == "ERROR":
            # error: consider next chunks
            continue

        try:
            # success: get the chunk
            data = networking.recvChunk(s, chunkSize)
        except (socket.timeout, RuntimeError):
            consecutiveErrors += 1
            print("Error receiving chunk {}".format(chunkID))
            continue

        try:
            # if file doesnt't exist, open create it
            peerCore.pathCreationLock.acquire()
            f = open(newFilepath, 'wb')
            peerCore.pathCreationLock.release()

            # write chunk into new file
            f.seek(chunkID*CHUNK_SIZE)
            f.write(data)
            f.close()

            # record successfully reception of the chunk
            file.missingChunks.remove(chunkID)
            file.availableChunks.append(chunkID)

        except FileNotFoundError:
            continue

    networking.closeConnection(s, peerCore.peerID)


def endDownload(file, newFilepath):
    """
    Handles end download operation.
    :param file: File object
    :param newFilepath: temporary path of the new file
    :return: void
    """

    # manage empty file case
    if file.filesize == 0:
        # create an empty file
        peerCore.pathCreationLock.acquire()
        f = open(newFilepath, 'wb')
        f.close()
        peerCore.pathCreationLock.release()

    # remove previous version of the file (if any)
    if os.path.exists(file.filepath):
        os.remove(file.filepath)

    # rename the new file into the right name
    os.rename(newFilepath, file.filepath)


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
