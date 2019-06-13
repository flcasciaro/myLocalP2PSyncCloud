import os
import time
from collections import deque
from threading import Lock

import fileManagement
import peerCore

# Data structure where sync operations will be scheduled
# I'm not using a Queue object (that is thread-safe and don't need a lock)
# because it is not iterable
queue = deque()
queueLock = Lock()

# Global variable used to stop the sync scheduler thread
stop = False

# Data structure that keep tracks of synchronization threads
# key : groupName_filename
# values: dict()    ->      groupName
#                           stop
syncThreads = dict()
syncThreadsLock = Lock()

# Maximum number of synchronization threads working at the same time
MAX_SYNC_THREAD = 5

def scheduler():

    while True:

        if stop:
            break
        else:
            # extract action from the queue until is empty or all syncThreads are busy
            while not queue.empty() and len(syncThreads) < MAX_SYNC_THREAD:
                queueLock.acquire()
                task = queue.get()

                queueLock.release()
                # assign task to a sync thread
                #     # ignore file in non active groups
        #     if groupsList[file.groupName]["status"] != "ACTIVE":
        #         continue
        #
        #     # if the file is not already in sync
        #     if file.syncLock.acquire(blocking=False):
        #
        #         # Sync file if status is "D" and there are available threads
        #         syncThreadsLock.acquire()
        #         if file.status == "D" and len(syncThreads) < MAX_SYNC_THREAD:
        #             # start a new synchronization thread if there are less
        #             # than MAX_SYNC_THREAD already active threads
        #             syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
        #             syncThread.daemon = True
        #             key = file.groupName + "_" + file.filename
        #             syncThreads[key] = dict()
        #             syncThreads[key]["groupName"] = file.groupName
        #             syncThreads[key]["stop"] = False
        #             syncThread.start()
        #         syncThreadsLock.release()
        #         file.syncLock.release()



                syncThreadsLock.release()
            time.sleep(1)

def stopScheduler():

    global stop
    stop = True


def addedFiles(message):

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        filesInfo = eval(message[2])

        if groupName in peerCore.groupsList:
            if peerCore.groupsList[groupName]["status"] == "ACTIVE":
                for fileInfo in filesInfo:

                    path = peerCore.scriptPath + "filesSync/" + groupName

                    # create the path if it doesn't exist
                    peerCore.pathCreationLock.acquire()
                    if not os.path.exists(path):
                        print("Creating the path: " + path)
                        os.makedirs(path)
                    peerCore.pathCreationLock.release()

                    filepath = path + "/" + fileInfo["filename"]

                    filename = fileInfo["filename"].split("/")[-1]

                    # create file Object
                    file = fileManagement.File(groupName=groupName, filename=filename,
                                               filepath=filepath, filesize=fileInfo["filesize"],
                                               timestamp=fileInfo["timestamp"], status="D",
                                               previousChunks=list())

                    peerCore.localGroupTree.addNode(fileInfo["filename"], file)

                    task = "SYNC {} {}".format(groupName, fileInfo["filename"])
                    queueLock.acquire()
                    queue.put(task)
                    queueLock.release()

                answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer

def removedFiles(message):
    pass


def updatedFiles(message):

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        filesInfo = eval(message[2])

        if groupName in peerCore.groupsList:
            if peerCore.groupsList[groupName]["status"] == "ACTIVE":
                for fileInfo in filesInfo:

                    file = peerCore.localFileTree.getGroup(groupName).findNode(fileInfo["filename"])

                    file.filesize = fileInfo["filesize"]
                    file.timestamp = fileInfo["timestamp"]
                    file.status = "D"
                    file.previousChunks = list()

                    task = "SYNC {} {}".format(groupName, fileInfo["filename"])
                    queueLock.acquire()
                    queue.put(task)
                    queueLock.release()

                answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer