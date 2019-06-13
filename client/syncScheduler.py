from queue import Queue
from threading import Lock

# Data structure where sync operations will be scheduled
queue = Queue()

# Global variable used to stop the sync scheduler thread
stopSync = False

# Data structure that keep tracks of synchronization threads
# key : groupName_filename
# values: dict()    ->      groupName
#                           stop
syncThreads = dict()
syncThreadsLock = Lock()

# Maximum number of synchronization threads working at the same time
MAX_SYNC_THREAD = 5

def scheduler():
    pass
    # while True:
    #
    #     if stopSync:
    #         break
    #     else:
    #         # extract action from the queue until is empty or all syncThreads are busy
    #         while not queue.empty() and len(syncThreads) < MAX_SYNC_THREAD:
    #             task = queue.get()
    #             # assign task to a sync thread
    #             #     # ignore file in non active groups
    #     #     if groupsList[file.groupName]["status"] != "ACTIVE":
    #     #         continue
    #     #
    #     #     # if the file is not already in sync
    #     #     if file.syncLock.acquire(blocking=False):
    #     #
    #     #         # Sync file if status is "D" and there are available threads
    #     #         syncThreadsLock.acquire()
    #     #         if file.status == "D" and len(syncThreads) < MAX_SYNC_THREAD:
    #     #             # start a new synchronization thread if there are less
    #     #             # than MAX_SYNC_THREAD already active threads
    #     #             syncThread = Thread(target=fileSharing.downloadFile, args=(file,))
    #     #             syncThread.daemon = True
    #     #             key = file.groupName + "_" + file.filename
    #     #             syncThreads[key] = dict()
    #     #             syncThreads[key]["groupName"] = file.groupName
    #     #             syncThreads[key]["stop"] = False
    #     #             syncThread.start()
    #     #         syncThreadsLock.release()
    #     #         file.syncLock.release()
    #
    #
    #
    #             syncThreadsLock.release()
    #     time.sleep(1)


def addedFiles(message):
    pass

def removedFiles(message):
    pass

def updatedFiles(message):
    pass