import os
import time
from collections import deque
from threading import Thread, Lock

import fileManagement
import fileSharing
import peerCore

# Data structure where sync operations will be scheduled
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


class syncTask:

    def __init__(self, groupName, fileTreePath, timestamp):

        self.groupName = groupName
        self.fileTreePath = fileTreePath
        self.timestamp = timestamp

    def toString(self):

        return "SYNC {} {} {}".format(self.groupName, self.fileTreePath, self.timestamp)

    def isOutdated(self, newTask):
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
    global queue, stop

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
                        syncThread = Thread(target=fileSharing.downloadFile, args=(fileNode.file, task.timestamp))
                        syncThread.daemon = True
                        key = task.groupName + "_" + task.fileTreePath
                        syncThreads[key] = dict()
                        syncThreads[key]["groupName"] = task.groupName
                        syncThreads[key]["stop"] = False
                        syncThread.start()
                    syncThreadsLock.release()
                    fileNode.file.syncLock.release()

                else:
                    print("Re-appending task: ", task.toString())
                    appendTask(task)

            time.sleep(1)


def stopScheduler():
    global stop
    stop = True


def appendTask(task, checkOutdated=False):
    """
    Append a task to queue.
    If checkOutdated is True verify all the task in the queue
    and remove outdated tasks (smaller timestamp for the same file).
    Furthermore, if task is outdated don't append it.
    :param task: task to insert
    :param checkOutdated: boolean (if True enable the check)
    :return: void
    """

    global queue
    queueLock.acquire()

    if checkOutdated:
        # remove outdated tasks and check if task is outdated or not
        deleteIndex = list()
        outdated = False

        for i in range(0, queue.count()):
            # check if task is outdated respect to task-i
            if task.isOutdated(queue[i]):
                outdated = True
                break

            # check if task-i is outdated respect to task
            if queue[i].isOutdated(task):
                deleteIndex.append(i)

        if not outdated:
            # delete outdated tasks and append the new one
            for index in deleteIndex:
                del queue[index]
            queue.append(task)

    else:
        # append task without any check
        queue.append(task)

    queueLock.release()


def removeGroupTask(groupName):
    """
    Remove from the task queue all the tasks acting on file of a specific group.
    It's useful after a group disconnect or leave operation.
    :param groupName: name of the group
    :return: void
    """

    global queue
    queueLock.acquire()
    queue = deque([t for t in queue if t.groupName != groupName])
    queueLock.release()


def removeAllTasks():
    global queue
    queueLock.acquire()
    queue = deque()
    queueLock.release()


def removeSyncThread(key):
    syncThreadsLock.acquire()
    if key in syncThreads:
        del syncThreads[key]
    syncThreadsLock.release()


def getThreadStatus(key):
    syncThreadsLock.acquire()
    if key in syncThreads:
        return syncThreads[key]["stop"]
    syncThreadsLock.release()


def stopSyncThread(key):
    syncThreadsLock.acquire()
    if key in syncThreads:
        syncThreads[key]["stop"] = True
    syncThreadsLock.release()


def stopSyncThreadByGroup(groupName):
    syncThreadsLock.acquire()
    for thread in syncThreads.values():
        if thread["groupName"] == groupName:
            thread["stop"] = True
    syncThreadsLock.release()


def stopAllSyncThreads():
    syncThreadsLock.acquire()
    for thread in syncThreads.values():
        thread["stop"] = True
    syncThreadsLock.release()


def addedFiles(message):
    global queue

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
                    appendTask(newTask)

                answer = "OK - FILES SUCCESSFULLY ADDED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    print(answer)
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
                    stopSyncThread(key)

                answer = "OK - FILES SUCCESSFULLY REMOVED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    print(answer)
    return answer


def updatedFiles(message):
    global queue

    try:
        messageFields = message.split(" ", 2)
        groupName = messageFields[1]
        filesInfo = eval(messageFields[2])

        if groupName in peerCore.groupsList:
            if peerCore.groupsList[groupName]["status"] == "ACTIVE":
                for fileInfo in filesInfo:

                    fileNode = peerCore.localFileTree.getGroup(groupName).findNode(fileInfo["treePath"])

                    if fileNode is None:
                        continue

                    fileNode.file.syncLock.acquire()

                    fileNode.file.filesize = fileInfo["filesize"]
                    fileNode.file.timestamp = fileInfo["timestamp"]
                    fileNode.file.status = "D"
                    fileNode.file.previousChunks = list()

                    # stop possible synchronization thread acting on the file
                    key = groupName + "_" + fileInfo["treePath"]
                    stopSyncThread(key)

                    fileNode.file.syncLock.release()

                    # create new syncTask
                    newTask = syncTask(groupName, fileInfo["treePath"], fileInfo["timestamp"])
                    appendTask(newTask, True)

                answer = "OK - SYNC TASK LOADED"
            else:
                answer = "ERROR - CURRENTLY I'M NOT ACTIVE"
        else:
            answer = "ERROR - GROUP DOESN'T EXIST"

    except IndexError:
        answer = "ERROR - INVALID REQUEST"

    print(answer)
    return answer
