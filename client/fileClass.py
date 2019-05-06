import datetime
import os
import stat


class File:

    def __init__(self, filename, filepath, filesize, lastModified):
        self.filename = filename
        self.filepath = filepath
        self.filesize = filesize
        self.lastModified = lastModified

def getFileStat(filepath):
    """This function returnes filesize and lastModifiedTime of a parameter filepath"""
    st = os.stat(filepath)
    """convert the retrieved timestamp into a Y/M/D h/m/s datetime"""
    lastModifiedTime = datetime.datetime.fromtimestamp(st[stat.ST_MTIME])
    return st[stat.ST_SIZE], lastModifiedTime

