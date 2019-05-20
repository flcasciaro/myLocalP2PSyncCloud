"""Peer GUI code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import datetime
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
        self.groupsList.setHeaderLabels(["GroupName","Active/Total Peers","Role","Status"])
        self.groupsList.setAlternatingRowColors(True)
        self.groupsList.setMinimumWidth(self.width*3/10)
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
        self.removeFile.clicked.connect(self.removeFileHandler)
        self.changeRole.clicked.connect(self.changeRoleHandler)
        self.leaveButton.clicked.connect(self.leaveGroupHandler)
        self.disconnectButton.clicked.connect(self.disconnectGroupHandler)

        self.signals.refresh.connect(self.refreshGUI)

        peerCore.setPeerID()
        serverReachable = peerCore.findServer()

        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))

        self.loadInititalFileManager()
        self.show()

        while not serverReachable:
            """Create dialog box in order to set server coordinates"""
            ok = False
            while not ok:
                coordinates, ok = QInputDialog.getText(self, 'Server coordinates',
                                                       'Enter Server IP Address and Server Port\nUse the format: serverIP:ServerPort')

            peerCore.setServerCoordinates(coordinates)
            serverReachable = peerCore.serverIsReachable()
            if not serverReachable:
                QMessageBox.about(self, "Alert", "Server not reachable or coordinates not valid")

        self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        self.fillGroupManager()

        reply = QMessageBox.question(self, 'Message', "Do you want to restore last session groups?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.restoreAllHandler()

        if not peerCore.startSync(self.signals):
            exit(-1)

        self.refreshThread.start()

    def refreshHandler(self):

        while not self.stopRefresh:
            for i in range(0,10):
                if self.stopRefresh:
                    exit()
                else:
                    time.sleep(1)
            self.signals.refreshEmit()

    def refreshGUI(self):

        self.fillGroupManager()
        if not self.fileList.isHidden():
            self.loadFileManager()

        
    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            """kill the refresh thread"""
            self.stopRefresh = True
            self.refreshThread.join()
            peerCore.disconnectPeer()
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

        peerCore.retrieveGroups()

        self.groupsList.clear()

        """This function update groups list for the peer, retrieving information from the server"""     

        for group in peerCore.activeGroupsList.values():
            item = QTreeWidgetItem([group["name"],
                        str(group["active"]) + "/" + str(group["total"]),
                        group["role"], "ACTIVE"])
            self.groupsList.addTopLevelItem(item)

        for group in peerCore.restoreGroupsList.values():
            item = QTreeWidgetItem([group["name"],
                        str(group["active"]) + "/" + str(group["total"]),
                        group["role"], "RESTORABLE"])
            self.groupsList.addTopLevelItem(item)

        for group in peerCore.otherGroupsList.values():
            item = QTreeWidgetItem([group["name"],
                        str(group["active"]) + "/" + str(group["total"]),
                        "/", "NOT JOINED"])
            self.groupsList.addTopLevelItem(item)



    def restoreAllHandler(self):

        if len(peerCore.restoreGroupsList) != 0:
            reply = QMessageBox.question(self, 'Message', "Are you sure?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
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

        if len(groupName) == 0 or  len(groupName.split()) != 1:
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
                                        peerCore.activeGroupsList[self.groupName]["role"],
                                        peerCore.activeGroupsList[self.groupName]["active"],
                                        peerCore.activeGroupsList[self.groupName]["total"]))
        
        self.fileListLabel.show()

        "Fills the files list"

        self.fileList.show()
        self.fillFileList()

        if peerCore.activeGroupsList[self.groupName]["role"].upper() == "RW":
            self.selectFile.show()
            self.removeFile.show()
            self.syncButton.show()
            self.syncAllButton.show()

        if peerCore.activeGroupsList[self.groupName]["role"].upper() == "MASTER":
            self.selectFile.show()
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

        peerCore.updateLocalFileList()

        self.fileList.clear()
        for file in peerCore.localFileList.values():
            if file.groupName == self.groupName:
                if file.status == "S":
                    syncStatus = "Synchronized"
                elif file.status == "U":
                    syncStatus = "Not synchronized"
                elif file.status == "D":
                    syncStatus = "Synchronizing: " + str(file.progress) + "%"
                item = QTreeWidgetItem([file.filename, file.filepath, str(file.filesize),
                                        file.lastModified, syncStatus])
                self.fileList.addTopLevelItem(item)


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
        file = dlg.getOpenFileName(self, 'Add file to the group', 'c:\\')
        length = len(file[0].split("/"))
        filename = file[0].split("/")[length-1]
        if peerCore.addFile(file[0], self.groupName):
            self.loadFileManager()
            self.addLogMessage("File {} added to group {}".format(filename, self.groupName))
        else:
            QMessageBox.about(self, "Error", "Cannot add the selected file!")

    def removeFileHandler(self):

        if self.fileList.currentItem() is not None:
            filename = self.fileList.currentItem().text(0)
            if peerCore.removeFile(filename, self.groupName):
                self.addLogMessage("File {} removed from group {}".format(filename, self.groupName))
                self.loadFileManager()
            else:
                QMessageBox.about(self, "Error", "Cannot remove the selected file!")
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
                    #if the targetPeer is active send it a message in order to make it able to refresh the window
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
                self.loadInititalGroupInfo()
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
                self.loadInititalGroupInfo()
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
            for i in range(0,self.fileList.count()):
                filename = self.fileList.item(i).text().split()[0]
                peerCore.syncFile(filename,self.groupName)



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



if __name__ == '__main__':
    app = QApplication([])
    darkgray_stylesheet = qdarkgraystyle.load_stylesheet()
    app.setStyleSheet(darkgray_stylesheet)
    window = myP2PSyncCloud()
    sys.exit(app.exec_())