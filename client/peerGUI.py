"""Peer GUI code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import datetime
import os
import sys
import time
from threading import Thread

import qdarkgraystyle
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import mySignals
import peerCore

firstTip = "Double click an active group in order to access the group file manager"
secondTip = "Double click a not active group in order to show information about the group"
statusLabel = "ROLE: {} \t PEERS (ACTIVE/TOTAL): {}/{}"
MAX_TRY = 3


class myP2PSyncCloud(QMainWindow):

    def __init__(self):
        super().__init__()
        """Window properties definition"""
        self.title = "myP2PSyncCloud"
        self.left = 300
        self.top = 40
        self.width = 1000
        self.height = 500

        """Window main structure definition"""
        self.verticalSplitter = QSplitter(Qt.Vertical)
        self.horizontalSplitter = QSplitter()
        self.groupManager = QWidget()
        self.fileManager = QWidget()
        self.actionsList = QListWidget()

        """Define a vertical box layout for the two main parts of the window"""
        self.groupManagerLayout = QVBoxLayout()
        self.fileManagerLayout = QVBoxLayout()

        """Declaration of UI object in the groupManager frame"""
        self.peerLabel = QLabel()
        self.serverLabel = QLabel()

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

        """Declaration of UI object in the fileManager frame"""
        self.fileManagerLabel1 = QLabel(firstTip)
        self.fileManagerLabel2 = QLabel(firstTip)
        self.fileListLabel = QLabel("FILES LIST")
        self.fileList = QTreeWidget()
        self.addRemoveLayout = QHBoxLayout()
        self.selectFile = QPushButton("ADD FILE")
        self.selectDir = QPushButton("ADD DIR")
        self.removeFile = QPushButton("REMOVE FILE")
        self.syncLayout = QHBoxLayout()
        self.syncButton = QPushButton("SYNC SELECTED FILE")
        self.syncAllButton = QPushButton("SYNC ALL GROUP FILES")
        self.peersListLabel = QLabel("PEERS LIST")
        self.peersList = QTreeWidget()
        self.changeRoleLayout = QHBoxLayout()
        self.selectRole = QComboBox()
        self.changeRole = QPushButton("CHANGE ROLE")
        self.leaveDisconnectLayout = QHBoxLayout()
        self.leaveButton = QPushButton("LEAVE GROUP")
        self.disconnectButton = QPushButton("DISCONNECT")

        self.signals = mySignals.mySig()
        self.groupName = ""
        self.refreshThread = Thread(target=self.refreshHandler, args=())
        self.stopRefresh = False

        self.initUI()

    def initUI(self):
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

        self.groupManagerLayout.addWidget(self.peerLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.serverLabel, alignment=Qt.AlignCenter)
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

        self.selectRole.addItem("CHANGE MASTER")
        self.selectRole.addItem("ADD MASTER")
        self.selectRole.addItem("MAKE IT RW")
        self.selectRole.addItem("MAKE IT RO")

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
        self.fileManagerLayout.addLayout(self.addRemoveLayout)
        self.syncLayout.addWidget(self.syncButton)
        self.syncLayout.addWidget(self.syncAllButton)
        self.fileManagerLayout.addLayout(self.syncLayout)
        self.fileManagerLayout.addSpacing(20)
        self.fileManagerLayout.addWidget(self.peersListLabel, alignment=Qt.AlignCenter)
        self.peersList.setHeaderLabels(["PeerID", "Role", "Status"])
        self.peersList.setAlternatingRowColors(True)
        self.peersList.setMinimumWidth(self.width / 2)
        self.peersList.setMinimumHeight(100)
        self.fileManagerLayout.addWidget(self.peersList)
        self.changeRoleLayout.addWidget(self.selectRole)
        self.changeRoleLayout.addWidget(self.changeRole)
        self.fileManagerLayout.addLayout(self.changeRoleLayout)
        self.fileManagerLayout.addSpacing(30)
        self.leaveDisconnectLayout.addWidget(self.leaveButton)
        self.leaveDisconnectLayout.addWidget(self.disconnectButton)
        self.fileManagerLayout.addLayout(self.leaveDisconnectLayout)

        self.restoreAllButton.clicked.connect(self.restoreAllHandler)
        self.createGroupButton.clicked.connect(self.createGroupHandler)
        self.resetCreateButton.clicked.connect(self.resetCreateHandler)
        self.groupsList.itemDoubleClicked.connect(self.groupDoubleClicked)
        self.syncButton.clicked.connect(self.syncButtonHandler)
        self.syncAllButton.clicked.connect(self.syncAllButtonHandler)
        self.selectFile.clicked.connect(self.addFileHandler)
        self.selectDir.clicked.connect(self.addDirHandler)
        self.removeFile.clicked.connect(self.removeFileHandler)
        self.changeRole.clicked.connect(self.changeRoleHandler)
        self.leaveButton.clicked.connect(self.leaveGroupHandler)
        self.disconnectButton.clicked.connect(self.disconnectGroupHandler)

        self.signals.refresh.connect(self.refreshAll)

        peerCore.setPeerID()
        serverReachable = peerCore.findServer()

        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))

        self.loadInititalFileManager()
        self.show()

        nrTry = 0
        while not serverReachable:
            """Create dialog box in order to set server coordinates"""
            ok = False
            while not ok:
                coordinates, ok = QInputDialog.getText(self, 'Server coordinates',
                                                       'Enter Server IP Address and Server Port\nUse the format: serverIP:ServerPort')
                if not ok:
                    nrTry += 1
                    if nrTry == MAX_TRY:
                        exit()
            if peerCore.setServerCoordinates(coordinates):
                serverReachable = peerCore.serverIsReachable()
            else:
                nrTry += 1
                if nrTry == MAX_TRY:
                    exit()
                continue
            if not serverReachable:
                QMessageBox.about(self, "Alert", "Server not reachable or coordinates not valid")

        self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        peerCore.retrieveGroups()
        self.fillGroupManager()

        self.restoreAllHandler()

        if not peerCore.startSync():
            exit(-1)

        peerCore.updateLocalFileList()

        self.refreshThread.daemon = True
        self.refreshThread.start()

    def refreshHandler(self):

        while True:
            for i in range(0, 10):
                if self.stopRefresh:
                    return
                else:
                    time.sleep(1)
            self.signals.refreshEmit()

    def refreshAll(self):
        print("REFRESHING ALL")
        peerCore.retrieveGroups()
        self.fillGroupManager()
        peerCore.updateLocalFileList()
        if not self.fileList.isHidden():
            self.loadFileManager()

    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.stopRefresh = True
            peerCore.disconnectPeer()
            timeout = 5
            msgBox = TimerMessageBox(timeout, self)
            msgBox.exec_()
            event.accept()
        else:
            event.ignore()

    def loadInititalFileManager(self):
        self.fileManagerLabel1.setText(firstTip)
        self.fileManagerLabel2.setText(secondTip)
        self.hideFileManager()

    def hideFileManager(self):
        self.fileListLabel.hide()
        self.fileList.hide()
        self.selectFile.hide()
        self.selectDir.hide()
        self.removeFile.hide()
        self.syncButton.hide()
        self.syncAllButton.hide()
        self.peersListLabel.hide()
        self.peersList.hide()
        self.selectRole.hide()
        self.changeRole.hide()
        self.leaveButton.hide()
        self.disconnectButton.hide()

    def fillGroupManager(self):

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

        groupName = self.createGroupName.text()
        groupTokenRW = self.createTokenRW.text()
        groupTokenRWConfirm = self.createTokenRWConfirm.text()
        groupTokenRO = self.createTokenRO.text()
        groupTokenROConfirm = self.createTokenROConfirm.text()

        if len(groupName) == 0 or len(groupName.split()) != 1:
            QMessageBox.about(self, "Error", "Invalid group name!")
        elif len(groupTokenRW) == 0 or len(groupTokenRO) == 0 \
                or groupTokenRW != groupTokenRWConfirm or groupTokenRO != groupTokenROConfirm:
            QMessageBox.about(self, "Error", "Invalid tokens!")
        else:
            if peerCore.createGroup(groupName, groupTokenRW, groupTokenRO):
                self.fillGroupManager()
                self.resetCreateHandler()
                self.groupName = groupName
                self.loadFileManager()
                self.addLogMessage("Group {} successfully created".format(groupName))
            else:
                QMessageBox.about(self, "Error", "Group creation failed!")

    def resetCreateHandler(self):

        self.createGroupName.setText("Enter single word GroupName")
        self.createTokenRW.clear()
        self.createTokenRWConfirm.clear()
        self.createTokenRO.clear()
        self.createTokenROConfirm.clear()

    def groupDoubleClicked(self, item):
        self.groupName = item.text(0)
        status = item.text(3).upper()
        if status == "ACTIVE":
            self.loadFileManager()
        elif status == "RESTORABLE":
            self.restoreHandler()
        else:
            self.joinHandler()

    def loadFileManager(self):

        self.hideFileManager()

        self.fileManagerLabel1.setText("FILE MANAGER GROUP {}".format(self.groupName))
        self.fileManagerLabel2.setText(statusLabel.format(
            peerCore.groupsList[self.groupName]["role"],
            peerCore.groupsList[self.groupName]["active"],
            peerCore.groupsList[self.groupName]["total"]))

        self.fileListLabel.show()

        "Fills the files list"

        self.fileList.show()
        self.fillFileList()

        if peerCore.groupsList[self.groupName]["role"].upper() == "RW":
            self.selectFile.show()
            self.selectDir.show()
            self.removeFile.show()
            self.syncButton.show()
            self.syncAllButton.show()

        if peerCore.groupsList[self.groupName]["role"].upper() == "MASTER":
            self.selectFile.show()
            self.selectDir.show()
            self.removeFile.show()
            self.syncButton.show()
            self.syncAllButton.show()
            self.peersListLabel.show()
            self.fillPeersList()
            self.peersList.show()
            self.selectRole.show()
            self.changeRole.show()

        self.leaveButton.show()
        self.disconnectButton.show()

    def fillPeersList(self):

        peersList = peerCore.retrievePeers(self.groupName, selectAll=True)

        if peersList is not None:
            self.peersList.clear()
            for peer in peersList:
                status = "Active" if peer["active"] else "NotActive"
                item = QTreeWidgetItem([peer["peerID"], peer["role"], status])
                self.peersList.addTopLevelItem(item)
        else:
            QMessageBox.about(self, "Error", "Error while retrieving list of peers!")

    def fillFileList(self):

        self.fileList.clear()
        for file in peerCore.localFileList.values():
            if file.groupName == self.groupName:
                if file.status == "S":
                    syncStatus = "Synchronized"
                elif file.status == "U":
                    syncStatus = "Not synchronized"
                elif file.status == "D":
                    syncStatus = "Synchronizing: " + str(file.progress) + "%"

                if len(file.filename.split("/")) == 1:
                    filename = file.filename.split("/")[-1]
                    item = QTreeWidgetItem([filename, file.filepath, str(file.filesize),
                                            file.getLastModifiedTime(), syncStatus])
                    self.fileList.addTopLevelItem(item)
                else:
                    # file belongs to a directory
                    # for each directory on the name:
                    #       find the directory in the list (if not exist add it)
                    parent = None
                    dirTree = file.filename.split("/")
                    length = len(dirTree) - 1

                    for index in range(0, length):

                        node = dirTree[index]

                        item = QTreeWidgetItem([node, "", "", "", ""])

                        items = self.fileList.findItems(node, Qt.MatchExactly | Qt.MatchRecursive, 0)
                        if len(items) == 0:
                            # directory is not listed yet: add it
                            if parent is not None:
                                parent.addChild(item)
                            else:
                                self.fileList.addTopLevelItem(item)
                            # item.setExpanded(True)
                            parent = item
                        else:
                            # one or more items match: check if parents are right

                            found = False

                            for i in items:
                                j = index - 1
                                match = True
                                dirToCheck = i.parent()
                                while j >= 0:
                                    if dirTree[j] != dirToCheck.text(0):
                                        match = False
                                        break
                                if match:
                                    found = True
                                    parent = i
                                    break

                            if not found:
                                if parent is not None:
                                    parent.addChild(item)
                                else:
                                    self.fileList.addTopLevelItem(item)
                                parent = item

                    # add file to the directory item
                    filename = file.filename.split("/")[-1]
                    item = QTreeWidgetItem([filename, file.filepath, str(file.filesize),
                                            file.getLastModifiedTime(), syncStatus])
                    parent.addChild(item)

    def restoreHandler(self):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to restore the group {} ?"
                                     .format(self.groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the restoreGroup function passing the self.groupName as parameter"""
            if peerCore.restoreGroup(self.groupName, delete=True):
                self.fillGroupManager()
                self.loadFileManager()
                self.addLogMessage("Group {} restored".format(self.groupName))
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")

    def joinHandler(self):

        token, okPressed = QInputDialog.getText(self, "Get token", "Your token:", QLineEdit.Password, "")
        if okPressed and token != '':
            if peerCore.joinGroup(self.groupName, token):
                self.fillGroupManager()
                self.loadFileManager()
                self.addLogMessage("Group {} joined".format(self.groupName))
            else:
                QMessageBox.about(self, "Error", "Wrong token!")

    def addFileHandler(self):

        dlg = QFileDialog()
        file = dlg.getOpenFileName(self, "Add file to the group", "/")
        if file[0] == "":
            # no file picked
            return
        length = len(file[0].split("/"))
        filename = file[0].split("/")[length - 1]

        # convert to a "UNIX-like" path
        filepath = file[0].replace("\\", "/")

        if peerCore.addFile(filepath, self.groupName):
            self.loadFileManager()
            self.addLogMessage("File {} added to group {}".format(filename, self.groupName))
        else:
            QMessageBox.about(self, "Error", "Cannot add the selected file!")

    def addDirHandler(self):

        dlg = QFileDialog()
        directory = dlg.getExistingDirectory(self, "Add directory to the group", "/")
        if directory == "":
            # no directory picked
            return
        length = len(directory.split("/"))
        dirName = directory.split("/")[length - 1]
        filepaths = list()
        for root, dirs, files in os.walk(directory):
            for name in files:
                filepaths.append(os.path.join(root, name).replace("\\", "/"))
        peerCore.addDir(filepaths, self.groupName, directory.replace("\\", "/"))

        self.loadFileManager()
        self.addLogMessage("Directory {} added to group {}".format(dirName, self.groupName))

    def removeFileHandler(self):

        if self.fileList.currentItem() is not None:
            if self.fileList.currentItem().text(1) != "":
                filename = self.fileList.currentItem().text(0)
                parent = self.fileList.currentItem().parent()
                while parent is not None:
                    filename = parent.text(0) + "/" + filename
                    parent = parent.parent()
                if peerCore.removeFile(filename, self.groupName):
                    self.addLogMessage("File {} removed from group {}".format(filename, self.groupName))
                    self.loadFileManager()
                else:
                    QMessageBox.about(self, "Error", "Cannot remove the selected file!")
            else:
                QMessageBox.about(self, "Error", "You cannot delete a directory")
        else:
            QMessageBox.about(self, "Error", "You must select a file from the list")

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

    def syncButtonHandler(self):
        if self.fileList.currentItem() is not None:
            filename = self.fileList.currentItem().text(0)
            file = peerCore.localFileList[self.groupName + "_" + filename]
            if file.status == "U":
                if peerCore.updateFile(file):
                    self.addLogMessage("File {} synchronized".format(filename))
                else:
                    QMessageBox.about(self, "Error", "It was not possible to synchronize the file")
        else:
            QMessageBox.about(self, "Error", "You must select a file from the list")

    def syncAllButtonHandler(self):
        if self.fileList.count() == 0:
            QMessageBox.about(self, "Error", "There aren't files in the group!")
        else:
            for i in range(0, self.fileList.count()):
                filename = self.fileList.item(i).text().split()[0]
                peerCore.updateFile(filename, self.groupName)

    def addLogMessage(self, message):
        modMessage = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " >>> " + message
        """keep track of just the last 5 messages"""
        if self.actionsList.count() == 5:
            item = self.actionsList.item(4)
            item.setText(modMessage)
        else:
            self.actionsList.addItem(modMessage)
        self.actionsList.sortItems(order=Qt.DescendingOrder)
        QMessageBox.about(self, "Notification", message)

class TimerMessageBox(QMessageBox):
    def __init__(self, timeout=3, parent=None):
        super(TimerMessageBox, self).__init__(parent)
        self.setWindowTitle("Wait")
        self.setMinimumHeight(40)
        self.setMinimumWidth(70)
        self.time_to_wait = timeout
        self.setText("Saving session status...")
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


if __name__ == '__main__':
    app = QApplication([])
    darkgray_stylesheet = qdarkgraystyle.load_stylesheet()
    app.setStyleSheet(darkgray_stylesheet)
    window = myP2PSyncCloud()
    sys.exit(app.exec_())
