import json

import fileManagement


class FileTree:

    def __init__(self):

        self.groups = dict()

    def addGroup(self, groupTree):

        groupName = groupTree.nodeName
        self.groups[groupName] = groupTree

    def getGroup(self, groupName):

        if groupName in self.groups:
            return self.groups[groupName]
        else:
            return None

    def print(self):

        for group in self.groups:
            group.print(0)


class Node:

    def __init__(self, nodeName, isDir, file = None):

        self.nodeName = nodeName
        self.isDir = isDir

        if self.isDir:
            self.file = None
            self.childs = dict()
        else:
            self.file = file
            self.childs = None

    def addChild(self, child):

        if self.isDir:
            if child.nodeName not in self.childs:
                self.childs[child.nodeName] = child
            else:
                print("ERROR: CHILD ALREADY ADDED")
        else:
            print("ERROR: TRYING TO ADD A CHILD TO A FILE NODE")

    def print(self, level):

        levelStr = "-" * level * 5
        levelStr += ">"

        if self.isDir:
            print("{} Dirname: {}".format(levelStr, self.nodeName))
            for child in self.childs.values():
                child.print(level+1)
        else:
            print("{} Filename: {}".format(levelStr, self.file.filename))

    def findNode(self, treePath):

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
        :return: void
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
                    return
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
                    return



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

        treePaths = list()

        if self.isDir:
            for child in self.childs.values():
                treePaths.extend(child.getFileTreePathsR(""))
        else:
            return None

        return treePaths


    def getFileTreePathsR(self, treePath):

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

    for group in fileTreeJson:
        groupTree = Node(group["nodeName"], True, None)
        fillNode(groupTree, group["childs"])
        fileTree.addGroup(groupTree)

    del fileTreeJson

    print("Previous session information successfully retrieved")
    return fileTree


def fillNode(node, childs):

    for child in childs:
        if child["isDir"]:
            newNode = Node(child["nodeName"], True, None)
            fillNode(newNode, child["childs"])
        else:
            fileInfo = child["info"]
            file = fileManagement.File(fileInfo["groupName"], fileInfo["treePath"],
                                       fileInfo["filename"], fileInfo["filepath"],
                                       fileInfo["filesize"], fileInfo["timestamp"],
                                       fileInfo["status"], fileInfo["previousChunks"])
            newNode = Node(child["nodeName"], False, file)
        node.addChild(newNode)


def saveFileStatus(fileTree, sessionFile):

    fileTreeJson = list()

    for group in fileTree.groups.values():

        groupInfo = dict()
        groupInfo["nodeName"] = group.nodeName
        groupInfo["isDir"] = True
        groupInfo["childs"] = list()
        groupInfo["info"] = dict()

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


