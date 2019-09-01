"""
Project: myP2PSync
@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC

This code handles the client (GUI) of a myP2PSync user (peer).
Can be run using: (sudo) python3 pathTo/myP2PSyncClient.py

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
import os
import sys
import time
from threading import Thread

import qdarkgraystyle
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import peerCore

firstTip = "Double click an active group in order to access the group file manager"
secondTip = "Double click a not active group in order to access the group"
statusLabel = "ROLE: {} \t PEERS (ACTIVE/TOTAL): {}/{}"

#  defines the maximum number of attempts to reach the tracker server
MAX_TRY = 3

# define the number of seconds among two GUI refresh operation
REFRESHING_TIME = 10


class myP2PSync(QMainWindow):
    """
    This class represents the whole GUI and all its handlers.
    """

    def __init__(self):
        super().__init__()
        # Window properties definition
        self.title = "myP2PSync"
        self.left = 200
        self.top = 40
        self.width = 1000
        self.height = 500

        # Window main structure definition
        self.verticalSplitter = QSplitter(Qt.Vertical)
        self.horizontalSplitter = QSplitter()
        self.groupManager = QWidget()
        self.fileManager = QWidget()
        self.actionsList = QListWidget()

        # Define a vertical box layout for the two main parts of the window
        self.groupManagerLayout = QVBoxLayout()
        self.fileManagerLayout = QVBoxLayout()

        # Declaration of UI objects in the groupManager frame
        self.peerLabel = QLabel()
        self.trackerLabel = QLabel()

        self.groupsLabel = QLabel("LIST OF GROUPS")
        self.groupsList = QTreeWidget()
        self.restoreAllButton = QPushButton("RESTORE ALL GROUPS")

        self.createGroupLayout = QFormLayout()
        self.createGroupLabel = QLabel("CREATE A GROUP: ")
        self.createGroupName = QLineEdit("Enter single word GroupName")
        self.tokenRWLabel = QLabel("Enter token for RW")
        self.createTokenRW = QLineEdit("")
        self.tokenRWLabelConfirm = QLabel("Confirm token for RW")
        self.createTokenRWConfirm = QLineEdit("")
        self.tokenROLabel = QLabel("Enter token for RO")
        self.createTokenRO = QLineEdit("")
        self.tokenROLabelConfirm = QLabel("Confirm token for RO")
        self.createTokenROConfirm = QLineEdit("")
        self.createGroupButton = QPushButton("CREATE GROUP")
        self.resetCreateButton = QPushButton("RESET")

        # Declaration of UI objects in the fileManager frame
        self.fileManagerLabel1 = QLabel(firstTip)
        self.fileManagerLabel2 = QLabel(firstTip)
        self.fileListLabel = QLabel("FILES LIST")
        self.fileList = QTreeWidget()
        self.addRemoveLayout = QHBoxLayout()
        self.selectFile = QPushButton("ADD FILE")
        self.selectDir = QPushButton("ADD DIRECTORY")
        self.removeFile = QPushButton("REMOVE FILE")
        self.removeDir = QPushButton("REMOVE DIRECTORY")
        self.syncLayout = QHBoxLayout()
        self.syncFileButton = QPushButton("SYNC SELECTED FILE")
        self.syncDirButton = QPushButton("SYNC SELECTED DIRECTORY")
        self.syncAllButton = QPushButton("SYNC ALL GROUP FILES")
        self.peersListLabel = QLabel("PEERS LIST")
        self.peersList = QTreeWidget()
        self.changeRoleLayout = QHBoxLayout()
        self.selectRole = QComboBox()
        self.changeRole = QPushButton("CHANGE ROLE")
        self.leaveDisconnectLayout = QHBoxLayout()
        self.leaveButton = QPushButton("LEAVE GROUP")
        self.disconnectButton = QPushButton("DISCONNECT")

        self.signals = mySig()
        self.server = None
        self.groupName = ""

        self.refreshThread = Thread(target=self.backgroundRefresh, args=())
        self.stopRefresh = False

        self.initUI()

    def initUI(self):
        """
        Initialize the GUI
        """

        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setCentralWidget(self.verticalSplitter)

        self.horizontalSplitter.addWidget(self.groupManager)
        self.groupManager.setMinimumWidth(300)
        self.horizontalSplitter.addWidget(self.fileManager)

        self.verticalSplitter.addWidget(self.horizontalSplitter)
        self.verticalSplitter.addWidget(self.actionsList)

        self.actionsList.setMaximumHeight(70)

        self.groupManager.setLayout(self.groupManagerLayout)
        self.fileManager.setLayout(self.fileManagerLayout)

        # initialize groupManager
        self.groupManagerLayout.addWidget(self.peerLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.trackerLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addSpacing(25)
        self.groupManagerLayout.addWidget(self.groupsLabel, alignment=Qt.AlignCenter)
        self.groupsList.setHeaderLabels(["GroupName", "Active/Total Peers", "Role", "Status"])
        self.groupsList.setAlternatingRowColors(True)
        self.groupsList.setMinimumWidth(self.width * 3 / 10)
        self.groupsList.setMinimumHeight(150)
        self.groupManagerLayout.addWidget(self.groupsList)
        self.groupManagerLayout.addSpacing(15)
        self.groupManagerLayout.addWidget(self.restoreAllButton)
        self.groupManagerLayout.addSpacing(25)

        # initialize Create Group form
        self.createTokenRW.setEchoMode(QLineEdit.Password)
        self.createTokenRWConfirm.setEchoMode(QLineEdit.Password)
        self.createTokenRO.setEchoMode(QLineEdit.Password)
        self.createTokenROConfirm.setEchoMode(QLineEdit.Password)
        self.createGroupLayout.addRow(self.createGroupLabel, self.createGroupName)
        self.createGroupLayout.addRow(self.tokenRWLabel, self.createTokenRW)
        self.createGroupLayout.addRow(self.tokenRWLabelConfirm, self.createTokenRWConfirm)
        self.createGroupLayout.addRow(self.tokenROLabel, self.createTokenRO)
        self.createGroupLayout.addRow(self.tokenROLabelConfirm, self.createTokenROConfirm)
        self.createGroupLayout.addRow(self.resetCreateButton, self.createGroupButton)
        self.groupManagerLayout.addLayout(self.createGroupLayout)
        self.groupManagerLayout.addSpacing(10)

        # initialize fileManager
        self.fileManagerLayout.addWidget(self.fileManagerLabel1, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addSpacing(5)
        self.fileManagerLayout.addWidget(self.fileManagerLabel2, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addSpacing(20)
        self.fileManagerLayout.addWidget(self.fileListLabel, alignment=Qt.AlignCenter)
        self.fileList.setHeaderLabels(["Filename", "Filepath", "Filesize", "LastModified", "Status"])
        self.fileList.setAlternatingRowColors(True)
        self.fileList.setMinimumWidth(self.width / 2)
        self.fileList.setMinimumHeight(100)
        self.fileManagerLayout.addWidget(self.fileList)
        self.fileManagerLayout.addSpacing(20)
        self.addRemoveLayout.addWidget(self.selectFile)
        self.addRemoveLayout.addWidget(self.selectDir)
        self.addRemoveLayout.addWidget(self.removeFile)
        self.addRemoveLayout.addWidget(self.removeDir)
        self.fileManagerLayout.addLayout(self.addRemoveLayout)
        self.syncLayout.addWidget(self.syncFileButton)
        self.syncLayout.addWidget(self.syncDirButton)
        self.syncLayout.addWidget(self.syncAllButton)
        self.fileManagerLayout.addLayout(self.syncLayout)
        self.fileManagerLayout.addSpacing(20)
        self.fileManagerLayout.addWidget(self.peersListLabel, alignment=Qt.AlignCenter)
        self.peersList.setHeaderLabels(["PeerID", "Role", "Status"])
        self.peersList.setAlternatingRowColors(True)
        self.peersList.setMinimumWidth(self.width / 2)
        self.peersList.setMinimumHeight(100)
        self.fileManagerLayout.addWidget(self.peersList, alignment=Qt.AlignCenter)
        self.selectRole.addItem("CHANGE MASTER")
        self.selectRole.addItem("ADD MASTER")
        self.selectRole.addItem("MAKE IT RW")
        self.selectRole.addItem("MAKE IT RO")
        self.changeRoleLayout.addWidget(self.selectRole)
        self.changeRoleLayout.addWidget(self.changeRole)
        self.fileManagerLayout.addLayout(self.changeRoleLayout)
        self.fileManagerLayout.addSpacing(30)
        self.leaveDisconnectLayout.addWidget(self.leaveButton)
        self.leaveDisconnectLayout.addWidget(self.disconnectButton)
        self.fileManagerLayout.addLayout(self.leaveDisconnectLayout)

        # connect actions on widgets to handlers
        self.restoreAllButton.clicked.connect(self.restoreAllHandler)
        self.createGroupButton.clicked.connect(self.createGroupHandler)
        self.resetCreateButton.clicked.connect(self.resetCreateHandler)
        self.groupsList.itemDoubleClicked.connect(self.groupDoubleClicked)
        self.selectFile.clicked.connect(self.addFileHandler)
        self.selectDir.clicked.connect(self.addDirHandler)
        self.removeFile.clicked.connect(self.removeFileHandler)
        self.removeDir.clicked.connect(self.removeDirHandler)
        self.syncFileButton.clicked.connect(self.syncFileHandler)
        self.syncDirButton.clicked.connect(self.syncDirHandler)
        self.syncAllButton.clicked.connect(self.syncAllHandler)
        self.changeRole.clicked.connect(self.changeRoleHandler)
        self.leaveButton.clicked.connect(self.leaveGroupHandler)
        self.disconnectButton.clicked.connect(self.disconnectGroupHandler)

        # connect the refresh signal signal to its handler
        self.signals.refresh.connect(self.refreshHandler)

        # set and show peerID
        peerCore.setPeerID()
        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))

        # try to obtain tracker coordinates
        if peerCore.findTracker():
            trackerReachable = peerCore.trackerIsReachable()
        else:
            trackerReachable = False

        self.loadInititalFileManager()
        self.show()

        nrTry = 0
        while not trackerReachable:
            # Show a dialog box where user can set tracker coordinates
            ok = False
            while not ok:
                coordinates, ok = QInputDialog.getText(self, "Tracker coordinates",
                                                       "Enter Tracker IP Address and Tracker Port\nUse the format: trackerIP:trackerPort")
                if not ok:
                    nrTry += 1
                    if nrTry == MAX_TRY:
                        exit()
            if peerCore.setTrackerCoordinates(coordinates):
                trackerReachable = peerCore.trackerIsReachable()
            else:
                nrTry += 1
                if nrTry == MAX_TRY:
                    exit()
                continue
            if not trackerReachable:
                QMessageBox.about(self, "Alert", "Tracker not reachable or coordinates not valid")

        self.trackerLabel.setText("Connected to tracker at {}:{}".format(peerCore.trackerAddr[0], peerCore.trackerAddr[1]))

        # start the peerServer and register peer coordinates on the tracker
        self.server = peerCore.startPeer()
        if self.server is None:
            exit(-1)

        # retrieve groups info from the Tracker and update windows
        peerCore.retrieveGroups()
        self.fillGroupManager()

        # show to the user the possibility to restore all the groups
        self.restoreAllHandler()

        # start the background refreshing thread
        self.refreshThread.daemon = True
        self.refreshThread.start()

    def backgroundRefresh(self):
        """
        These function is executed for all the time the client is running
        by a secondary thread. Every second the thread check if the client is
        still running and every REFRESHING_TIME seconds emits a refresh signal.
        """

        while True:
            for i in range(0, REFRESHING_TIME):
                if self.stopRefresh:
                    return
                else:
                    time.sleep(1)
            self.signals.refreshEmit()

    def refreshHandler(self):
        """
        Refresh groupManager and fileManager
        """
        peerCore.retrieveGroups()
        self.fillGroupManager()
        if not self.fileList.isHidden():
            self.loadFileManager()

    def closeEvent(self, event):
        """
        Handler for the closing operation (after a click on the 'X' in the window)
        :param event: the closing event generated
        """

        # confirm message box
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # stop the peer server
            self.server.stopServer()

            # handles the peer disconnection
            t = Thread(target=peerCore.peerExit, args=())
            t.daemon = True
            t.start()

            # stop the background refreshing thread
            self.stopRefresh = True

            # show a pop-up message
            timeout = 5
            msgBox = TimerMessageBox("Saving session status...", timeout, self)
            msgBox.exec_()

            event.accept()
        else:
            event.ignore()

    def loadInititalFileManager(self):
        """
        Load the empty fileManager
        """

        self.fileManagerLabel1.setText(firstTip)
        self.fileManagerLabel2.setText(secondTip)
        self.hideFileManager()

    def hideFileManager(self):
        """
        Hide all the fileManager components
        """
        self.fileListLabel.hide()
        self.fileList.hide()
        self.selectFile.hide()
        self.selectDir.hide()
        self.removeFile.hide()
        self.removeDir.hide()
        self.syncFileButton.hide()
        self.syncDirButton.hide()
        self.syncAllButton.hide()
        self.peersListLabel.hide()
        self.peersList.hide()
        self.selectRole.hide()
        self.changeRole.hide()
        self.leaveButton.hide()
        self.disconnectButton.hide()

    def fillGroupManager(self):
        """
        Fill the groupManager with groups information
        """

        self.groupsList.clear()

        itemsActive = list()
        itemsRestorable = list()
        itemsOther = list()

        for group in peerCore.groupsList.values():
            if group["status"] == "ACTIVE":
                itemsActive.append(QTreeWidgetItem([group["name"],
                                                    str(group["active"]) + "/" + str(group["total"]),
                                                    group["role"], "ACTIVE"]))
            elif group["status"] == "RESTORABLE":
                itemsRestorable.append(QTreeWidgetItem([group["name"],
                                                        str(group["active"]) + "/" + str(group["total"]),
                                                        group["role"], "RESTORABLE"]))
            else:
                itemsOther.append(QTreeWidgetItem([group["name"],
                                                   str(group["active"]) + "/" + str(group["total"]),
                                                   "/", "NOT JOINED"]))

        for item in itemsActive:
            self.groupsList.addTopLevelItem(item)
        for item in itemsRestorable:
            self.groupsList.addTopLevelItem(item)
        for item in itemsOther:
            self.groupsList.addTopLevelItem(item)

    def restoreAllHandler(self):
        """
        Allows the user to restore all the restorable groups
        """

        # show a message box
        reply = QMessageBox.question(self, 'Message', "Do you want to restore all the groups?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:

            restorable = 0

            for group in peerCore.groupsList.values():
                if group["status"] == "RESTORABLE":
                    restorable += 1

            if restorable > 0:

                groupsRestored = peerCore.restoreAll()
                if groupsRestored == "":
                    self.addLogMessage("It was not possible to restore any group")
                else:
                    self.addLogMessage("Groups {} restored".format(groupsRestored))
                self.fillGroupManager()
            else:
                QMessageBox.about(self, "Alert", "You don't have joined groups that can be restored")

    def createGroupHandler(self):
        """
        Collect and verify all the inputs in the createGroup form and
        in case everything is ok create the group
        """

        # collects inputs
        groupName = self.createGroupName.text()
        groupTokenRW = self.createTokenRW.text()
        groupTokenRWConfirm = self.createTokenRWConfirm.text()
        groupTokenRO = self.createTokenRO.text()
        groupTokenROConfirm = self.createTokenROConfirm.text()

        # check inputs
        if len(groupName) == 0 or len(groupName.split()) != 1:
            QMessageBox.about(self, "Error", "Invalid group name!")
        elif len(groupTokenRW) == 0 or len(groupTokenRO) == 0 \
                or groupTokenRW != groupTokenRWConfirm or groupTokenRO != groupTokenROConfirm:
            QMessageBox.about(self, "Error", "Invalid tokens!")
        elif groupName in peerCore.groupsList:
            QMessageBox.about(self, "Error", "GroupName already used!")
        else:
            # create groups and reload windows in case of success
            if peerCore.createGroup(groupName, groupTokenRW, groupTokenRO):
                self.fillGroupManager()
                self.resetCreateHandler()
                self.groupName = groupName
                self.loadFileManager()
                self.addLogMessage("Group {} successfully created".format(groupName))
            else:
                QMessageBox.about(self, "Error", "Group creation failed!")

    def resetCreateHandler(self):
        """
        Reset the crreateGroup form
        """
        self.createGroupName.setText("Enter single word GroupName")
        self.createTokenRW.clear()
        self.createTokenRWConfirm.clear()
        self.createTokenRO.clear()
        self.createTokenROConfirm.clear()

    def groupDoubleClicked(self, item):
        """
        Handle the double-clicking action on a group in the groupManager
        """

        self.groupName = item.text(0)
        status = item.text(3).upper()
        if status == "ACTIVE":
            self.loadFileManager()
        elif status == "RESTORABLE":
            self.restoreHandler()
        else:
            self.joinHandler()

    def restoreHandler(self):
        """
        Restore a restorable group and reload the window
        """

        # confirm message box
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to restore the group {} ?"
                                     .format(self.groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            # call the restoreGroup function passing the self.groupName as parameter
            # in case of success reload the window
            if peerCore.restoreGroup(self.groupName):
                self.fillGroupManager()
                self.loadFileManager()
                self.addLogMessage("Group {} restored".format(self.groupName))
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")

    def joinHandler(self):
        """
        Handler for the join group action (triggered by clicking on an active group)
        """

        # show a form where the user can insert a token
        token, okPressed = QInputDialog.getText(self, "Get token", "Your token:", QLineEdit.Password, "")
        if okPressed and token != '':
            # try to join the group: in case of success reload the window
            if peerCore.joinGroup(self.groupName, token):
                self.fillGroupManager()
                self.loadFileManager()
                self.addLogMessage("Group {} joined".format(self.groupName))
            else:
                QMessageBox.about(self, "Error", "Wrong token!")

    def loadFileManager(self):
        """
        Fills the fileManager part of the GUI.
        The set of information and buttons showed is related to the role
        of the peer.
        """

        # hide all the components
        self.hideFileManager()

        # set group information for all users
        self.fileManagerLabel1.setText("FILE MANAGER GROUP {}".format(self.groupName))
        self.fileManagerLabel2.setText(statusLabel.format(
            peerCore.groupsList[self.groupName]["role"],
            peerCore.groupsList[self.groupName]["active"],
            peerCore.groupsList[self.groupName]["total"]))

        # Fills the files list and show it to all users
        self.fileListLabel.show()
        self.fileList.show()
        self.fillFileList()

        if peerCore.groupsList[self.groupName]["role"].upper() != "RO":
            # show only to RW and Master
            self.selectFile.show()
            self.selectDir.show()
            self.removeFile.show()
            self.removeDir.show()
            self.syncFileButton.show()
            self.syncDirButton.show()
            self.syncAllButton.show()
            self.peersListLabel.show()
            self.fillPeersList()
            self.peersList.show()

        if peerCore.groupsList[self.groupName]["role"].upper() == "MASTER":
            # show only to Master
            self.selectRole.show()
            self.changeRole.show()

        # show to all users
        self.peersListLabel.show()
        self.fillPeersList()
        self.peersList.show()
        self.leaveButton.show()
        self.disconnectButton.show()

    def fillPeersList(self):

        peersList = peerCore.retrievePeers(self.groupName, selectAll=True)

        if peersList is not None:

            selectedItem = self.peersList.currentItem()
            if selectedItem is not None:
                selectedItemName = selectedItem.text(0)
            else:
                # no item selected
                selectedItemName = ""

            self.peersList.clear()
            for peer in peersList:
                status = "Active" if peer["active"] else "NotActive"
                item = QTreeWidgetItem([peer["peerID"], peer["role"], status])
                self.peersList.addTopLevelItem(item)
                if peer["peerID"] == selectedItemName:
                    self.peersList.setCurrentItem(item)

    def fillFileList(self):

        selectedItem = self.fileList.currentItem()
        if selectedItem is not None:
            selectedItemName = selectedItem.text(0)
        else:
            # no item selected
            selectedItemName = ""

        self.fileList.clear()

        groupTree = peerCore.localFileTree.getGroup(self.groupName)
        if groupTree is None:
            return

        for node in groupTree.childs.values():
            self.fileList.addTopLevelItem(generateFileListItem(node))

        allItems = self.fileList.findItems("*", Qt.MatchWrap | Qt.MatchWildcard | Qt.MatchRecursive)
        for item in allItems:
            item.setExpanded(True)
            if item.text(0) == selectedItemName:
                # print(item.text(0) + "   " + selectedItemName + "   match found")
                self.fileList.setCurrentItem(item)

    def addFileHandler(self):

        dlg = QFileDialog()
        files = dlg.getOpenFileNames(self, "Add file to the group", "/")
        if len(files[0]) == 0:
            # no file picked
            return

        filepaths = list()
        filenames = ""

        for file in files[0]:
            # get only the filename (remove dir path)
            filename = file.split("/")[-1]
            if peerCore.localFileTree.getGroup(self.groupName).findNode(filename) is not None:
                continue

            if len(filename.split(" ")) == 1:
                # convert to a "UNIX-like" path
                filepath = file.replace("\\", "/")
                filepaths.append(filepath)
                filenames = filenames + " " + filename + ","
            else:
                QMessageBox.about(self, "Error", "Cannot add file {}.. \
                                    filename cannot contains spaces!".format(filename))

        if len(filepaths) > 0:
            if peerCore.addFiles(self.groupName, filepaths, directory=""):
                self.loadFileManager()
                self.addLogMessage("Files {} added to group {}".format(filenames[:-1], self.groupName))
            else:
                QMessageBox.about(self, "Error", "Cannot add the selected files!")
        else:
            QMessageBox.about(self, "Error", "Cannot add the selected files!")

    def addDirHandler(self):

        dlg = QFileDialog()
        directory = dlg.getExistingDirectory(self, "Add directory to the group", "/")
        if directory == "":
            # no directory picked
            return

        dirName = directory.split("/")[-1]

        if len(dirName.split(" ")) == 1:
            if len(self.fileList.findItems(dirName, Qt.MatchExactly)) == 0:
                filepaths = list()
                for root, dirs, files in os.walk(directory):
                    for name in files:

                        # build the filepath and check that it doesn't contain space/s
                        filepath = os.path.join(root, name).replace("\\", "/")
                        if len(filepath.split(" ")) == 1:

                            filepaths.append(filepath)

                if peerCore.addFiles(self.groupName, filepaths, directory.replace("\\", "/")):
                    self.addLogMessage("Directory {} added to group {}".format(dirName, self.groupName))
                    self.loadFileManager()
                else:
                    QMessageBox.about(self, "Error", "It was not possible to add the directory {}".format(dirName))
            else:
                QMessageBox.about(self, "Error", "Cannot add the selected directory")
        else:
            QMessageBox.about(self, "Error", "Cannot add the selected directory.. name cannot contains spaces!")

    def removeFileHandler(self):

        if self.fileList.currentItem() is not None:
            if self.fileList.currentItem().text(1) != "":
                filename = self.fileList.currentItem().text(0)

                # build treePath
                treePath = filename
                parent = self.fileList.currentItem().parent()
                while parent is not None:
                    treePath = parent.text(0) + "/" + treePath
                    parent = parent.parent()

                treePaths = list()
                treePaths.append(treePath)

                if peerCore.removeFiles(self.groupName, treePaths):
                    self.addLogMessage("File {} removed from group {}".format(filename, self.groupName))
                    self.loadFileManager()
                else:
                    QMessageBox.about(self, "Error", "Cannot remove the selected file!")
            else:
                QMessageBox.about(self, "Error", "You cannot delete a directory")
        else:
            QMessageBox.about(self, "Error", "You must select a file from the list")

    def removeDirHandler(self):

        if self.fileList.currentItem() is not None:
            if self.fileList.currentItem().text(1) == "":

                dirName = self.fileList.currentItem().text(0)
                parent = self.fileList.currentItem().parent()

                treePath = dirName

                while parent is not None:
                    treePath = parent.text(0) + "/" + treePath
                    parent = parent.parent()

                treePaths = list()
                getDirFilenames(self.fileList.currentItem(), treePath, treePaths)

                if peerCore.removeFiles(self.groupName, treePaths):
                    self.addLogMessage("Directory {} removed from group {}".format(dirName, self.groupName))
                    self.loadFileManager()
                else:
                    QMessageBox.about(self, "Error", "Cannot remove the selected directory!")
            else:
                QMessageBox.about(self, "Error", "You've selected a file instead of a directory")
        else:
            QMessageBox.about(self, "Error", "You must select a dir from the list")

    def syncFileHandler(self):

        if self.fileList.currentItem() is not None:

            if self.fileList.currentItem().text(1) != "":

                filename = self.fileList.currentItem().text(0)
                treePath = filename
                parent = self.fileList.currentItem().parent()

                while parent is not None:
                    treePath = parent.text(0) + "/" + treePath
                    parent = parent.parent()

                file = peerCore.localFileTree.getGroup(self.groupName).findNode(treePath).file
                oldTimestamp = file.timestamp
                file.updateFileStat()

                files = list()

                if oldTimestamp < file.timestamp:
                    files.append((file, file.timestamp))
                    if peerCore.updateFiles(self.groupName, files):
                        self.addLogMessage("File {} synchronized".format(file.filename))
                        self.loadFileManager()
                    else:
                        self.addLogMessage("It was not possible to synchronize the file {}"
                                           .format(file.filename))
                else:
                    QMessageBox.about(self, "Info", "File has been already synchronized")
            else:
                QMessageBox.about(self, "Error", "You've selected a directory instead of a file")
        else:
            QMessageBox.about(self, "Error", "You must select a file from the list")

    def syncDirHandler(self):

        if self.fileList.currentItem() is not None:
            if self.fileList.currentItem().text(1) == "":

                dirName = self.fileList.currentItem().text(0)
                parent = self.fileList.currentItem().parent()

                while parent is not None:
                    dirName = parent.text(0) + "/" + dirName
                    parent = parent.parent()

                treePaths = list()
                files = list()
                getDirFilenames(self.fileList.currentItem(), dirName, treePaths)

                groupTree = peerCore.localFileTree.getGroup(self.groupName)

                for treePath in treePaths:
                    file = groupTree.findNode(treePath).file
                    oldTimestamp = file.timestamp
                    file.updateFileStat()

                    if oldTimestamp < file.timestamp:
                        files.append((file, file.timestamp))

                if len(files) > 0:

                    if peerCore.updateFiles(self.groupName, files):
                        self.addLogMessage("Dir {} synchronized".format(dirName))
                        self.loadFileManager()
                    else:
                        self.addLogMessage("It was not possible to synchronize the directory {}"
                                           .format(dirName))

                else:
                    QMessageBox.about(self, "Info", "All files have been already synchronized")
            else:
                QMessageBox.about(self, "Error", "You've selected a file instead of a directory")
        else:
            QMessageBox.about(self, "Error", "You must select a directory from the list")

    def syncAllHandler(self):

        if self.fileList.topLevelItemCount() == 0:
            QMessageBox.about(self, "Error", "There aren't files in the group!")
        else:

            for i in range(0, self.fileList.topLevelItemCount()):

                item = self.fileList.topLevelItem(i)
                treePaths = list()

                if item.text(1) == "":
                    # item is a directory: look for nested files and collect their filenames
                    getDirFilenames(item, item.text(0), treePaths)
                else:
                    # item is a file: append to filenames and try to synchronize
                    treePaths.append(item.text(0))

            files = list()

            for treePath in treePaths:

                file = peerCore.localFileTree.getGroup(self.groupName).findNode(treePath).file

                oldTimestamp = file.timestamp
                file.updateFileStat()

                if oldTimestamp < file.timestamp:
                    files.append((file, file.timestamp))

            if len(files) > 0:
                if peerCore.updateFiles(self.groupName, files):
                    self.addLogMessage("All files have been synchronized")
                    self.loadFileManager()
                else:
                    self.addLogMessage("It was not possible to synchronize all the files")
            else:
                QMessageBox.about(self, "Info", "All files are already synchronized")

    def changeRoleHandler(self):

        if self.peersList.currentItem() is not None:
            targetPeerID = self.peersList.currentItem().text(0)
            targetPeerStatus = self.peersList.currentItem().text(1)
            action = self.selectRole.currentText()
            reply = QMessageBox.question(self, 'Message', "Are you sure you want to apply \"{}\" command to {}?"
                                         .format(action, targetPeerID),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                """make action string compatible with peerCore.changePeer()"""
                action = action.replace(" ", "_")
                if peerCore.changeRole(self.groupName, targetPeerID, action.upper()):
                    self.addLogMessage("Role changed successfully in group {}".format(self.groupName))
                    self.loadFileManager()
                    # if the targetPeer is active send it a message in order to make it able to refresh the window
                    if targetPeerStatus == "ACTIVE":
                        pass
                else:
                    QMessageBox.about(self, "Error", "Something went wrong!")
        else:
            QMessageBox.about(self, "Error", "You must select a peer from the list")

    def leaveGroupHandler(self):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to leave the group {} ?"
                                     .format(self.groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the leaveGroup function passing the self.groupName as parameter"""
            if peerCore.leaveGroup(self.groupName):
                self.addLogMessage("Group {} left".format(self.groupName))
                self.fillGroupManager()
                self.loadInititalFileManager()
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")

    def disconnectGroupHandler(self):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to disconnect from the group {} ?"
                                     .format(self.groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the disconnectGroup function passing the self.groupName as parameter"""
            if peerCore.disconnectGroup(self.groupName):
                self.addLogMessage("Group {} disconnected".format(self.groupName))
                self.fillGroupManager()
                self.loadInititalFileManager()
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")

    def addLogMessage(self, message):
        """
        Add a message in the actionsList box
        :param message: text that will be added
        """

        # add current time to the message
        modMessage = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " >>> " + message

        # keep track of just the last 5 messages
        if self.actionsList.count() == 5:
            item = self.actionsList.item(4)
            item.setText(modMessage)
        else:
            self.actionsList.addItem(modMessage)
        self.actionsList.sortItems(order=Qt.DescendingOrder)

        # show message into a pop-up window
        QMessageBox.about(self, "Notification", message)


class TimerMessageBox(QMessageBox):
    """
    Custom class for a message box auto-expiring after <timeout> seconds.
    """

    def __init__(self, text, timeout=3, parent=None):
        super(TimerMessageBox, self).__init__(parent)
        self.setWindowTitle("Wait")
        self.setMinimumHeight(40)
        self.setMinimumWidth(70)
        self.time_to_wait = timeout
        self.setText(text)
        self.setStandardButtons(QMessageBox.NoButton)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()


class mySig(QObject):
    """
    Class for my refresh signal
    """

    # declare the signal
    refresh = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)

    def refreshEmit(self):
        # emit the signal
        self.refresh.emit()


def generateFileListItem(node):
    if node.isDir:
        item = QTreeWidgetItem([node.nodeName, "", "", "", ""])
        for child in node.childs.values():
            item.addChild(generateFileListItem(child))
    else:
        filesize, syncStatus = getFileLabels(node.file)
        item = QTreeWidgetItem([node.file.filename, node.file.filepath, filesize,
                                node.file.getLastModifiedTime(), syncStatus])

    return item


def getFileLabels(file):
    if file.filesize < 1024:
        filesize = str(file.filesize) + " B"
    elif file.filesize < 1048576:
        filesize = str(int(file.filesize / 1024)) + " KB"
    elif file.filesize < 1024 * 1048576:
        filesize = str(int(file.filesize / 1048576)) + " MB"
    else:
        filesize = str(int(file.filesize / (1024 * 1048576))) + " GB"

    if file.status == "S":
        syncStatus = "Synchronized"
    elif file.status == "U":
        syncStatus = "Not synchronized"
    elif file.status == "D":
        syncStatus = "Synchronizing: " + str(file.progress) + "%"

    return filesize, syncStatus


def getDirFilenames(item, dirName, treePaths):
    """
    Recursive function for traversing a QTreeWidget item
    while setting all the treePaths discovered into a treePaths list.
    :param item: is a QTreeWidgetItem object, which can have childs or not
    :param dirName: name of the parent directory
    :param treePaths: treePaths list
    :return: void
    """
    # for each child of the item
    for i in range(0, item.childCount()):
        if item.child(i).text(1) == "":
            # is a directory: call again the function recursively into the directory
            getDirFilenames(item.child(i), dirName + "/" + item.child(i).text(0), treePaths)
        else:
            # is a file: append the filename to the list
            treePaths.append(dirName + "/" + item.child(i).text(0))


if __name__ == '__main__':
    # declare the GUI application
    app = QApplication([])

    # apply the qdarkgraystyle
    darkgray_stylesheet = qdarkgraystyle.load_stylesheet()
    app.setStyleSheet(darkgray_stylesheet)

    # create the window object
    window = myP2PSync()

    # start the application
    sys.exit(app.exec_())
