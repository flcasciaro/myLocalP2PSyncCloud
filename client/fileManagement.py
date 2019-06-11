"""This code handles file-related operations in myP2PSync peers.
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""


import datetime
import json
import math
import os
import stat
from threading import Lock


# chunk size is fixed and equal for all the file
CHUNK_SIZE = 1048576          #    1 MB


class File:

    def __init__(self, groupName, filename, filepath, filesize, timestamp, status, previousChunks):

        # main properties (retrieved and stored in the session file)
        self.groupName = groupName
        self.filename = filename
        self.filepath = filepath
        self.filesize = int(filesize)
        self.timestamp = int(timestamp)
        self.status = status
        self.previousChunks = previousChunks

        # properties used for the file-sharing
        self.lastChunkSize = 0
        self.chunksNumber = 0
        self.missingChunks = None
        self.availableChunks = None
        self.progress = 0

        # used to lock the sync: avoid overlapping of sync process
        self.syncLock = Lock()


    def getLastModifiedTime(self):
        """convert the timestamp into a Y/M/D h/m/s datetime"""
        lastModifiedTime = datetime.datetime.fromtimestamp(self.timestamp)
        return str(lastModifiedTime)


    def updateFileStat(self):

        try:
            st = os.stat(self.filepath)
            self.filesize = st[stat.ST_SIZE]
            self.timestamp = st[stat.ST_MTIME]
        except OSError:
            print("File not found")
            

    def setProgress(self):
        try:
            self.progress = math.floor((len(self.availableChunks) / self.chunksNumber) * 100 )
        except ZeroDivisionError:
            #empty file
            self.progress = 100

    def initDownload(self):
        """initialize all the properties in order to work as peer (download/upload)"""
        try:
            self.chunksNumber = math.ceil(self.filesize / CHUNK_SIZE)
            self.lastChunkSize = self.filesize % CHUNK_SIZE
        except ZeroDivisionError:
            self.chunksNumber = 0
            self.lastChunkSize = 0

        self.missingChunks = list()
        self.availableChunks = list()
        for i in range(0, self.chunksNumber):
            if i in self.previousChunks:
                self.availableChunks.append(i)
            else:
                self.missingChunks.append(i)

        self.setProgress()

    def iHaveIt(self):
        """initialize all the properties in order to work as a seed for the file"""
        try:
            self.chunksNumber = math.ceil(self.filesize / CHUNK_SIZE)
            self.lastChunkSize = self.filesize % CHUNK_SIZE
        except ZeroDivisionError:
            self.chunksNumber = 0
            self.lastChunkSize = 0

        self.previousChunks = list()
        self.missingChunks = list()
        self.availableChunks = list()
        for i in range(0, self.chunksNumber):
            self.availableChunks.append(i)

        self.progress = 100


def getFileStat(filepath):
    """This function returnes filesize and lastModifiedTime of a parameter filepath"""
    try:
        st = os.stat(filepath)
        return st[stat.ST_SIZE], st[stat.ST_MTIME]
    except OSError:
        return None, None


def getPreviousFiles(previousSessionFile):

    fileList = dict()

    try:
        f = open(previousSessionFile, 'r')
        try:
            fileListJson = json.load(f)
        except ValueError:
            return fileList
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        return fileList

    for fileKey in fileListJson:
        fileList[fileKey] = File(fileListJson[fileKey]["groupName"],
                                 fileListJson[fileKey]["filename"],
                                 fileListJson[fileKey]["filepath"],
                                 fileListJson[fileKey]["filesize"],
                                 fileListJson[fileKey]["timestamp"],
                                 fileListJson[fileKey]["status"],
                                 fileListJson[fileKey]["previousChunks"])
    del fileListJson

    print("Previous session information successfully retrieved")

    return fileList


def saveFileStatus(previousSessionFile, fileList):

    fileListJson = dict()

    for fileKey in fileList:
        fileListJson[fileKey] = dict()
        fileListJson[fileKey]["groupName"] = fileList[fileKey].groupName
        fileListJson[fileKey]["filename"] = fileList[fileKey].filename
        fileListJson[fileKey]["filepath"] = fileList[fileKey].filepath
        fileListJson[fileKey]["filesize"] = fileList[fileKey].filesize
        fileListJson[fileKey]["timestamp"] = fileList[fileKey].timestamp
        fileListJson[fileKey]["status"] = fileList[fileKey].status
        fileListJson[fileKey]["previousChunks"] = fileList[fileKey].previousChunks

    print("Session information successfully saved")


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


