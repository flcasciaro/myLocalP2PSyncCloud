import json

import group


class FileTree:

    def __init__(self):

        self.groups = list()

    def addGroup(self, groupNode):

        self.groups.append(groupNode)

    def getGroup(self, groupName):

        for group in self.groups:
            if group.nodeName == groupName:
                return group
        return None

    def print(self):

        for group in self.groups:
            group.print()


class Node:

    def __init__(self, nodeName, isDir, file = None):

        self.nodeName = nodeName
        self.isDir = isDir

        if self.isDir:
            self.file = None
            self.childs = list()
        else:
            self.file = file
            self.childs = None

    def addChild(self, child):

        if self.isDir:
            self.childs.append(child)
        else:
            print("ERROR: TRYING TO ADD A CHILD TO A FILE NODE")

    def print(self):
        if self.isDir:
            print("Dirname: {}".format(self.nodeName))
            for child in self.childs:
                child.print()
        else:
            print("Filename: {} timestamp: {}".format(self.file.filename, self.file.timestamp))

    def findNode(self, filename):

        current = self
        found = False

        for name in filename.split("/"):
            for child in current.childs:
                if child.nodeName == name:
                    found = True
                    current = child
                    break

            # path not found
            if not found:
                return None

        return current

    def updateNode(self, filename, filesize, timestamp):

        node = self.findNode(filename)

        if node is not None:
            node.file.filesize = int(filesize)
            node.file.timestamp = int(timestamp)
        else:
            print("NODE NOT FOUND")

    def addNode(self, filename, filesize, timestamp):

        current = self
        i = 0
        n = len(filename.split("/"))
        for name in filename.split("/"):
            found = False
            for child in current.childs:
                if child.nodeName == name:
                    found = True
                    current = child
                    i += 1
                    break

            if not found:
                if i < n - 1:
                    # addDir node
                    node = Node(name, True)
                    current.addChild(node)
                    current = node
                    i += 1
                else:
                    # add File node
                    node = Node(name, False, group.FileInGroup(name, filesize, timestamp))
                    current.addChild(node)
                    return True
            else:
                # file node found
                if i == n - 1:
                    print("NODE ALREADY INSERTED")
                    return False


    def removeNode(self, filename):

        current = self
        found = False

        nodeList = list()
        nodeList.append(self)

        for name in filename.split("/"):
            for child in current.childs:
                if child.nodeName == name:
                    found = True
                    current = child
                    nodeList.append(current)
                    break

            # path not found
            if not found:
                print("NODE NOT FOUND")
                return

        last = nodeList.pop()
        del last.file
        parent = nodeList.pop()
        parent.childs.remove(last)
        del last

        while len(nodeList) > 0:
            last = parent
            parent = nodeList.pop()
            if len(parent.childs) <= 1:
                parent.childs.remove(last)
                del last
            else:
                break



def getFileStatus(previousSessionFile):

    fileTree = FileTree()
    try:
        f = open(previousSessionFile, 'r')
        try:
            fileTreeJson = json.load(f)
        except ValueError:
            return None
        f.close()
    except FileNotFoundError:
        print("No previous session session information found")
        return None

    for group in fileTreeJson:
        groupNode = Node(group["nodeName"], True, None)
        fillNode(groupNode, group["childs"])
        fileTree.addGroup(groupNode)

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
            file = group.FileInGroup(fileInfo["filename"], fileInfo["filesize"], fileInfo["timestamp"])
            newNode = Node(child["nodeName"], False, file)
        node.addChild(newNode)


def saveFileStatus(fileTree, sessionFile):

    fileTreeJson = list()

    for group in fileTree.groups:

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

    for child in childs:
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

            nestedInfo["info"]["filename"] = child.file.filename
            nestedInfo["info"]["filesize"] = child.file.filesize
            nestedInfo["info"]["timestamp"] = child.file.timestamp

        groupInfo["childs"].append(nestedInfo)



def treeToList(root):
    """
    This function map a tree into a list of dictionaries representing files.
    :param root: root node of the tree
    :return: list
    """

    nodeList = list()

    for child in root.childs:
        nodeList.extend(fillNodeList(child, ""))

    return nodeList


def fillNodeList(currentNode, treePath):

    nodeList = list()

    if treePath == "":
        treePath = currentNode.nodeName
    else:
        treePath = treePath + "/" + currentNode.nodeName

    if currentNode.isDir:
        for child in currentNode.childs:
            nodeList.extend(fillNodeList(child, treePath))
    else:
        nodeDict = dict()
        # nodeDict["nodeName"] = currentNode.nodeName
        nodeDict["treePath"] = treePath
        nodeDict["filename"] = currentNode.file.filename
        nodeDict["filesize"] = currentNode.file.filesize
        nodeDict["timestamp"] = currentNode.file.timestamp
        nodeList.append(nodeDict)

    return nodeList