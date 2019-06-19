import os
import time
from collections import deque
from threading import Thread, Lock

import fileManagement
import fileSharing
import peerCore

# Data structure where sync operations will be scheduled
queue = None
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

class syncTask:

    def __init__(self, groupName, fileTreePath, timestamp):

        self.groupName = groupName
        self.fileTreePath = fileTreePath
        self.timestamp = timestamp

    def print(self):

        print("SYNC {} {} {}".format(self.groupName, self.fileTreePath, self.timestamp))


    def outdatedSyncTask(self, newTask):
        """
        Check if a syncTask is outdated.
        A task is outdated if it refers to the same file of a new task but the timestamp is older (or equal).
        :param self: checked task
        :param newTask: new task
        :return: boolean (True if the task is outdated, otherwise False)
        """

        if self.groupName == newTask.groupName and self.fileTreePath == newTask.fileTreePath:
            if self.timestamp <= newTask.timestamp:
                return True

        return False


def scheduler():

    global queue
    queue = deque()

    while True:

        if stop:
            break
        else:
            # extract action from the queue until is empty or all syncThreads are busy
            while len(queue) > 0 and len(syncThreads) < MAX_SYNC_THREAD:

                queueLock.acquire()
                task = queue.popleft()
                queueLock.release()

                # skip task of non active groups
                if peerCore.groupsList[task.groupName]["status"] != "ACTIVE":
                    continue

                # assign task to a sync thread

                groupTree = peerCore.localFileTree.getGroup(task.groupName)
                fileNode = groupTree.findNode(task.fileTreePath)

                if fileNode is None:
                    # file has been removed
                    continue

                # if the file is not already in sync
                if fileNode.file.syncLock.acquire(blocking=False):

                    # Sync file if status is "D" and there are available threads
                    syncThreadsLock.acquire()
                    if fileNode.file.status == "D":
                        # start a new synchronization thread if there are less
                        # than MAX_SYNC_THREAD already active threads
                        syncThread = Thread(target=fileSharing.downloadFile, args=(fileNode.file, ))
                        syncThread.daemon = True
                        key = task.groupName + "_" + task.fileTreePath
                        syncThreads[key] = dict()
                        syncThreads[key]["groupName"] = task.groupName
                        syncThreads[key]["stop"] = False
                        syncThread.start()
                    syncThreadsLock.release()
                    fileNode.file.syncLock.release()

            time.sleep(1)

def stopScheduler():

    global stop
    stop = True


def addedFiles(message):

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        filesInfo = eval(messageFields[2])

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

                    treePath = fileInfo["treePath"]
                    filename = treePath.split("/")[-1]
                    filepath = path + "/" + treePath

                    # create file Object
                    file = fileManagement.File(groupName=groupName, treePath=treePath,
                                               filename=filename, filepath=filepath,
                                               filesize=fileInfo["filesize"],
                                               timestamp=fileInfo["timestamp"],
                                               status="D", previousChunks=list())

                    peerCore.localFileTree.getGroup(groupName).addNode(treePath, file)

                    # create new syncTask
                    newTask = syncTask(groupName, treePath, fileInfo["timestamp"])

                    queueLock.acquire()
                    # add newTask
                    queue.append(newTask)
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

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        fileTreePaths = eval(messageFields[2])

        if groupName in peerCore.groupsList:
            if peerCore.groupsList[groupName]["status"] == "ACTIVE":
                for treePath in fileTreePaths:

                    peerCore.localFileTree.getGroup(groupName).removeNode(treePath)

                    # stop possible synchronization thread acting on the file
                    key = groupName + "_" + treePath

                    syncThreadsLock.acquire()
                    if key in syncThreads:
                        syncThreads[key]["stop"] = True
                    syncThreadsLock.release()

                answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer


def updatedFiles(message):

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        filesInfo = eval(messageFields[2])

        if groupName in peerCore.groupsList:
            if peerCore.groupsList[groupName]["status"] == "ACTIVE":
                for fileInfo in filesInfo:

                    file = peerCore.localFileTree.getGroup(groupName).findNode(fileInfo["treePath"])

                    file.filesize = fileInfo["filesize"]
                    file.timestamp = fileInfo["timestamp"]
                    file.status = "D"
                    file.previousChunks = list()

                    # stop possible synchronization thread acting on the file
                    key = groupName + "_" + fileInfo["treePath"]

                    syncThreadsLock.acquire()
                    if key in syncThreads:
                        syncThreads[key]["stop"] = True
                    syncThreadsLock.release()

                    # create new syncTask
                    newTask = syncTask(groupName, fileInfo["treePath"], fileInfo["timestamp"])

                    queueLock.acquire()
                    # remove outdated syncTask
                    queue = [task for task in queue if not task.outdatedTask(newTask)]
                    # add newTask
                    queue.append(newTask)
                    queueLock.release()

                answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    return answer