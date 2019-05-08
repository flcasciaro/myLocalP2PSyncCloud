import datetime
import json
import os
import stat
from threading import Lock


class File:

    def __init__(self, groupName, filename, filepath, filesize, lastModified):
        self.groupName = groupName
        self.filename = filename
        self.filepath = filepath
        self.filesize = filesize
        self.lastModified = lastModified
        self.lock = Lock()

def getFileStat(filepath):
    """This function returnes filesize and lastModifiedTime of a parameter filepath"""
    st = os.stat(filepath)
    """convert the retrieved timestamp into a Y/M/D h/m/s datetime"""
    lastModifiedTime = datetime.datetime.fromtimestamp(st[stat.ST_MTIME])
    return st[stat.ST_SIZE], lastModifiedTime

def getPreviousFiles(previousSessionFile):

    try:
        f = open(previousSessionFile, 'r')
        try:
            filesStatus = json.load(f)
        except ValueError:
            return None
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        return None

    return filesStatus

def saveFileStatus(previousSessionFile, filesStatus):

    try:
        f = open(previousSessionFile, 'w')
        json.dump(filesStatus, f, indent=4)
        f.close()
    except FileNotFoundError:
        print("Error while saving the current file status")
        return False

    return True


