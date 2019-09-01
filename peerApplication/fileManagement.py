"""
Project: myP2PSync
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC

This code handles operations and attributes related to synchronized files in myP2PSync peers.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.
"""

import datetime
import math
import os
import stat
from threading import Lock

# chunk size is fixed and equal for all the file
CHUNK_SIZE = 1048576  # 1 MB


class File:
    """
    Class used to represent a sync file.
    """

    def __init__(self, groupName, treePath, filename, filepath, filesize, timestamp, status, previousChunks):

        # main properties (retrieved and stored in the session file)
        self.groupName = groupName
        self.treePath = treePath  # path in the fileTree used to reach the fileNode   e.g. dir1/dir2/file.txt
        self.filename = filename  # name of the file                                  e.g. file.txt
        self.filepath = filepath  # real path of the file                             e.g. C://home/dir1/dir2/file.txt
        self.filesize = int(filesize)  # filesize as number of bytes
        self.timestamp = int(timestamp)  # version of the file
        self.status = status  # status can be 'S' (synchronized) or 'D' (download, requires synchronization)
        self.previousChunks = previousChunks  # list of chunks already collected of the file after a partial sync process

        # properties used for the file-sharing
        self.lastChunkSize = 0  # size of the last chunk, can be different from CHUNK_SIZE
        self.chunksNumber = 0  # number of chunks that compose the file
        self.missingChunks = None  # list of chunks not retrieved yet
        self.availableChunks = None  # list of chunks already retrieved
        self.progress = 0  # synchronization progress: 0% (syncStart) -> 100% (syncComplete)

        self.syncLock = Lock()  # internal lock of the File object: used to synchronize threads acting on the file
        self.stopSync = False  # boolean value used to eventually stop a synchronization

    def getLastModifiedTime(self):
        """
        Convert the timestamp property into a Y/M/D h/m/s datetime.
        """

        lastModifiedTime = datetime.datetime.fromtimestamp(self.timestamp)
        return str(lastModifiedTime)

    def updateFileStat(self):
        """
        Update file stats retrieving OS values.
        Doesn't perform the action if the file is used by another sync thread
        or if the OS timestamp is smaller than the property timestamp
        (this last case can happens if another peer has already
        pushed an updated version of the file)
        :return: void
        """

        if self.syncLock.acquire(blocking=False):
            try:
                st = os.stat(self.filepath)
                newFilesize = st[stat.ST_SIZE]
                newTimestamp = st[stat.ST_MTIME]
                if newTimestamp > self.timestamp:
                    self.filesize = newFilesize
                    self.timestamp = newTimestamp
            except OSError:
                print("File not found")
            self.syncLock.release()

    def setProgress(self):
        """
        Set the progress property as function of the current status of a synchronization.
        :return: void
        """
        try:
            self.progress = math.floor((len(self.availableChunks) / self.chunksNumber) * 100)
        except ZeroDivisionError:
            # empty file
            self.progress = 100

    def initSync(self):
        """
        Initialize properties useful to download and upload chunks of the file.
        :return: void
        """

        if self.filesize == 0:
            # empty file
            self.chunksNumber = 0
            self.lastChunkSize = 0
        else:
            # calculate chunks number and last chunks size
            self.chunksNumber = math.ceil(self.filesize / CHUNK_SIZE)
            self.lastChunkSize = self.filesize % CHUNK_SIZE
            if self.lastChunkSize == 0:
                self.lastChunkSize = CHUNK_SIZE

        self.missingChunks = list()
        self.availableChunks = list()
        for i in range(0, self.chunksNumber):
            if i in self.previousChunks:
                self.availableChunks.append(i)
            else:
                self.missingChunks.append(i)

        self.previousChunks = list()
        self.setProgress()

    def initSeed(self):
        """
        Initialize all the properties in order to work as a seed for the file
        """

        if self.filesize == 0:
            # empty file
            self.chunksNumber = 0
            self.lastChunkSize = 0
        else:
            # calculate chunks number and last chunks size
            self.chunksNumber = math.ceil(self.filesize / CHUNK_SIZE)
            self.lastChunkSize = self.filesize % CHUNK_SIZE
            if self.lastChunkSize == 0:
                self.lastChunkSize = CHUNK_SIZE

        self.previousChunks = list()
        self.missingChunks = list()
        self.availableChunks = list()
        for i in range(0, self.chunksNumber):
            self.availableChunks.append(i)

        self.progress = 100


def getFileStat(filepath):
    """
    Returns filesize and lastModifiedTime of a file with filepath equal to the argument
    :param filepath: filepath string
    :return: filesize value, lastModifiedTime timestamp
    """
    try:
        st = os.stat(filepath)
        return st[stat.ST_SIZE], st[stat.ST_MTIME]
    except OSError:
        return None, None
