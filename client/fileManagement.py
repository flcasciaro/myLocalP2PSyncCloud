import datetime
import json
import os
import stat
from threading import Lock

"""define the size of a chunk: 1MB"""
chunkSize = 1024000

class File:

    def __init__(self, groupName, filename, filepath, filesize, lastModified, status):
        self.groupName = groupName
        self.filename = filename
        self.filepath = filepath
        self.filesize = filesize
        self.lastModified = str(lastModified)
        self.status = status
        """used to lock the sync: avoid overlapping of sync process"""
        self.syncLock = Lock()
        """used to lock the file during the file-sharing process"""
        self.fileLock = Lock()

    def updateFileStat(self):
        try:
            st = os.stat(self.filepath)
            """convert the retrieved timestamp into a Y/M/D h/m/s datetime"""
            lastModifiedTime = datetime.datetime.fromtimestamp(st[stat.ST_MTIME])
            self.lastModified = str(lastModifiedTime)
            self.filesize = st[stat.ST_SIZE]
        except OSError:
            print("File not found")


def getFileStat(filepath):
    """This function returnes filesize and lastModifiedTime of a parameter filepath"""
    try:
        st = os.stat(filepath)
        """convert the retrieved timestamp into a Y/M/D h/m/s datetime"""
        lastModifiedTime = datetime.datetime.fromtimestamp(st[stat.ST_MTIME])
        return st[stat.ST_SIZE], str(lastModifiedTime)
    except OSError:
        return None, None


def getPreviousFiles(previousSessionFile):

    try:
        f = open(previousSessionFile, 'r')
        try:
            fileListJson = json.load(f)
        except ValueError:
            return None
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        return None

    fileList = dict()
    for fileKey in fileListJson:
        fileList[fileKey] = File(fileListJson[fileKey]["groupName"],
                                 fileListJson[fileKey]["filename"],
                                 fileListJson[fileKey]["filepath"],
                                 fileListJson[fileKey]["filesize"],
                                 fileListJson[fileKey]["lastModified"],
                                 status = "")
    del fileListJson

    return fileList


def saveFileStatus(previousSessionFile, fileList):

    fileListJson = dict()

    for fileKey in fileList:
        fileListJson[fileKey] = dict()
        fileListJson[fileKey]["groupName"] = fileList[fileKey].groupName
        fileListJson[fileKey]["filename"] = fileList[fileKey].filename
        fileListJson[fileKey]["filepath"] = fileList[fileKey].filepath
        fileListJson[fileKey]["filesize"] = fileList[fileKey].filesize
        fileListJson[fileKey]["lastModified"] = fileList[fileKey].lastModified

    try:
        f = open(previousSessionFile, 'w')
        json.dump(fileListJson, f, indent=4)
        del fileListJson
        f.close()
    except FileNotFoundError:
        print("Error while saving the current file status")
        del fileListJson
        return False

    return True


