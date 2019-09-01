"""
Project: myP2PSync
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC

This code manages the organization of synchronized files in a myP2PSync client application.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.
"""


import json

import fileManagement


class FileTree:
    """
    Customized data structure used to store the organization of files in directories.
    It's similar to a tree with a set of roots.
    Each root is related to a group of the peer.
    """

    def __init__(self):
        """
        Initialize FileTree dictionary for group roots.
        """
        self.groups = dict()

    def addGroup(self, groupTree):
        """
        Add a group root to the user tree.
        :param groupTree: root of the group tree
        :return: void
        """
        groupName = groupTree.nodeName
        self.groups[groupName] = groupTree

    def getGroup(self, groupName):
        """
        Return the root of the group tree associated to the name groupName.
        :param groupName: name of the group
        :return: Node object representing the root of the group tree
        """
        if groupName in self.groups:
            return self.groups[groupName]
        else:
            return None

    def print(self):
        """
        Function used to print the tree.
        :return: void
        """
        for group in self.groups:
            group.print(0)


class Node:
    """
    Class used to describe the structure of a node of the FileTree.
    """

    def __init__(self, nodeName, isDir, file = None):

        # name of the node, e.g. filename or directory name
        self.nodeName = nodeName
        # boolean value: True -> node represents a directory, otherwise a file
        self.isDir = isDir

        if self.isDir:
            self.file = None
            # dict used to store all the nodes associated to file in the directory
            self.childs = dict()
        else:
            # File object
            self.file = file
            self.childs = None

    def addChild(self, child):
        """
        Add a child node to the self node dictionary.
        :param child: Node object
        :return: void
        """

        if self.isDir:
            if child.nodeName not in self.childs:
                self.childs[child.nodeName] = child
            else:
                print("ERROR: CHILD ALREADY ADDED")
        else:
            print("ERROR: TRYING TO ADD A CHILD TO A FILE NODE")

    def print(self, level):
        """
        Function used to print the files tree.
        :param level: level of the node in the tree in terms of depth
        :return: void
        """

        levelStr = "-" * level * 5
        levelStr += ">"

        if self.isDir:
            print("{} Dirname: {}".format(levelStr, self.nodeName))
            for child in self.childs.values():
                child.print(level+1)
        else:
            print("{} Filename: {}".format(levelStr, self.file.filename))

    def findNode(self, treePath):
        """
        Find and return a node following a path in the tree.
        :param treePath: it's the path to follow
        :return: Node object if found or None
        """
        current = self

        for name in treePath.split("/"):
            if name in current.childs:
                current = current.childs[name]
            else:
                # path not found
                return None

        return current


    def addNode(self, treePath, file):
        """
        Add a node in a tree with root in the node.
        If a directory node in the middle is not present, the function creates it.
        :param treePath: path to follow to reach where the node will be placed
        :param file: file Object
        :return: boolean (True for success, False for failure)
        """

        current = self
        treePathFields = treePath.split("/")
        n = len(treePathFields)
        # traverse the tree
        for i in range(0, n):
            field = treePathFields[i]

            if field in current.childs:
                if i == n - 1:
                    # file node found
                    print("NODE ALREADY INSERTED")
                    return False
                else:
                    current = current.childs[field]

            else:
                if i < n - 1:
                    # addDir node
                    node = Node(field, True)
                    current.addChild(node)
                    current = node
                else:
                    # add File node
                    node = Node(field, False, file)
                    current.addChild(node)
                    return True



    def removeNode(self, treePath, removeFileObj):
        """
        Remove a node from the tree with root in the node.
        :param treePath: path to follow to reach the node that will be removed
        :param removeFileObj: boolean value, if True remove also the file Object in the node
        :return: void
        """

        current = self

        # use a nodeList to store all the nodes in the middle
        # between the root and the node that will be removed
        nodeList = list()
        # append root
        nodeList.append(self)

        # traverse the tree
        for name in treePath.split("/"):

            if name in current.childs:
                current = current.childs[name]
                nodeList.append(current)

            else:
                print("NODE NOT FOUND")
                return

        last = nodeList.pop()
        if removeFileObj:
            # delete File object
            del last.file

        parent = nodeList.pop()
        # remove node from the parent dictionary
        del parent.childs[last.nodeName]
        # remove Node object
        del last

        # cut from the tree directory Node without childs
        while len(nodeList) > 0:
            last = parent
            parent = nodeList.pop()
            if len(last.childs) == 0:
                del parent.childs[last.nodeName]
                del last
            else:
                break


    def getFileTreePaths(self):
        """
        Return a list of all the treePath in the tree with root in self Node.
        :return: a list of treePaths
        """
        treePaths = list()

        if self.isDir:
            for child in self.childs.values():
                treePaths.extend(child.getFileTreePathsR(""))
        else:
            return None

        return treePaths


    def getFileTreePathsR(self, treePath):
        """
        Recursive function used by getFileTreePaths in order to
        extract the list of all the treePath inside a tree.
        :param treePath: treePath string
        :return: treePaths list
        """

        treePaths = list()

        if treePath == "":
            treePath = self.nodeName
        else:
            treePath = treePath + "/" + self.nodeName

        if self.isDir:
            for child in self.childs.values():
                treePaths.extend(child.getFileTreePathsR(treePath))
        else:
            treePaths.append(treePath)

        return treePaths



def getFileStatus(previousSessionFile):
    """
    Load a FileTree with information stored in a JSON file.
    :param previousSessionFile: name of the file
    :return: FileTree onject
    """

    fileTree = FileTree()

    try:
        f = open(previousSessionFile, 'r')
        try:
            fileTreeJson = json.load(f)
        except ValueError:
            return fileTree
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        return fileTree

    # convert the nested JSON dictionaries into a tree
    for group in fileTreeJson:
        # create root node for the group
        groupTree = Node(group["nodeName"], True, None)
        # fill the group tree
        fillNode(groupTree, group["childs"])
        # add the group tree to the main tree
        fileTree.addGroup(groupTree)

    del fileTreeJson

    print("Previous session information successfully retrieved")
    return fileTree


def fillNode(node, childs):
    """
    Recursively build a tree node.
    :param node: Node object
    :param childs: list of child dictionaries
    :return: void
    """

    for child in childs:
        if child["isDir"]:
            # directory node
            newNode = Node(child["nodeName"], True, None)
            fillNode(newNode, child["childs"])
        else:
            # file node
            fileInfo = child["info"]
            file = fileManagement.File(fileInfo["groupName"], fileInfo["treePath"],
                                       fileInfo["filename"], fileInfo["filepath"],
                                       fileInfo["filesize"], fileInfo["timestamp"],
                                       fileInfo["status"], fileInfo["previousChunks"])
            newNode = Node(child["nodeName"], False, file)
        node.addChild(newNode)


def saveFileStatus(fileTree, sessionFile):
    """
    Save the structure of a File Tree object into a JSON  file.
    :param fileTree: FileTree object
    :param sessionFile: name of the file
    :return: boolean (True for success)
    """

    fileTreeJson = list()

    # convert the tree into a nested dictionaries format (JSON-like)
    for group in fileTree.groups.values():

        # build a dict from a node
        groupInfo = dict()
        groupInfo["nodeName"] = group.nodeName
        groupInfo["isDir"] = True
        groupInfo["childs"] = list()
        groupInfo["info"] = dict()

        # handle possible childs node
        fillChildsInfo(groupInfo, group.childs)
        fileTreeJson.append(groupInfo)

    try:
        f = open(sessionFile, 'w')
        json.dump(fileTreeJson, f, indent=4)
        del fileTreeJson
        f.close()
    except FileNotFoundError:
        print("Error while saving the current file status")
        del fileTreeJson
        return False

    print("Session information successfully saved")
    return True


def fillChildsInfo(groupInfo, childs):
    """
    Fill recursively a dictionary with info about childs node.
    :param groupInfo: dictionary for a certain node
    :param childs: list of childs of the node
    :return: void
    """

    for child in childs.values():
        if child.isDir:
            nestedInfo = dict()
            nestedInfo["nodeName"] = child.nodeName
            nestedInfo["isDir"] = True
            nestedInfo["childs"] = list()
            nestedInfo["info"] = dict()

            fillChildsInfo(nestedInfo, child.childs)

        else:
            nestedInfo = dict()
            nestedInfo["nodeName"] = child.nodeName
            nestedInfo["isDir"] = False
            nestedInfo["childs"] = list()
            nestedInfo["info"] = dict()

            nestedInfo["info"]["groupName"] = child.file.groupName
            nestedInfo["info"]["treePath"] = child.file.treePath
            nestedInfo["info"]["filename"] = child.file.filename
            nestedInfo["info"]["filepath"] = child.file.filepath
            nestedInfo["info"]["filesize"] = child.file.filesize
            nestedInfo["info"]["timestamp"] = child.file.timestamp
            nestedInfo["info"]["status"] = child.file.status
            nestedInfo["info"]["previousChunks"] = child.file.previousChunks

        groupInfo["childs"].append(nestedInfo)


