"""Peer GUI code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import datetime
import sys

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
        self.width = 500
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

        self.activeGroupLabel = QLabel("List of ACTIVE groups")
        self.activeGroupList = QListWidget()
        self.otherGroupLabel = QLabel("List of OTHER groups")
        self.otherGroupList = QListWidget()
        self.restoreAllButton = QPushButton("RESTORE ALL GROUPS")

        self.createGroupLayout = QFormLayout()
        self.createGroupLabel = QLabel("Create a group: ")
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
        self.joinOrRestoreButton = QPushButton("")
        self.fileListLabel = QLabel("Files List")
        self.fileList = QListWidget()
        self.selectFile = QPushButton("ADD FILE")
        self.syncButton = QPushButton("SYNC FILE")
        self.peersListLabel = QLabel("Peers List")
        self.peersList = QListWidget()
        self.changeRoleLayout = QHBoxLayout()
        self.selectRole = QComboBox()
        self.changeRole = QPushButton("CHANGE ROLE")
        self.leaveButton = QPushButton("LEAVE GROUP")
        self.disconnectButton = QPushButton("DISCONNECT")

        self.signals = mySignals.mySig()

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

        self.groupManager.setLayout(self.groupManagerLayout)
        self.fileManager.setLayout(self.fileManagerLayout)

        self.groupManagerLayout.addWidget(self.peerLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.serverLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addSpacing(25)

        self.groupManagerLayout.addWidget(self.activeGroupLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.activeGroupList)
        self.groupManagerLayout.addSpacing(15)
        self.groupManagerLayout.addWidget(self.otherGroupLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.otherGroupList)
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
        self.groupManagerLayout.addLayout(self.createGroupLayout)
        self.groupManagerLayout.addWidget(self.createGroupButton)
        self.groupManagerLayout.addWidget(self.resetCreateButton)
        self.groupManagerLayout.addSpacing(10)

        self.selectRole.addItem("CHANGE MASTER")
        self.selectRole.addItem("ADD MASTER")
        self.selectRole.addItem("MAKE IT RW")
        self.selectRole.addItem("MAKE IT RO")

        self.fileManagerLayout.addSpacing(30)
        self.fileManagerLayout.addWidget(self.fileManagerLabel1, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addSpacing(5)
        self.fileManagerLayout.addWidget(self.fileManagerLabel2, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addSpacing(20)
        self.fileManagerLayout.addWidget(self.joinOrRestoreButton)
        self.fileManagerLayout.addSpacing(50)
        self.fileManagerLayout.addWidget(self.fileListLabel, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addWidget(self.fileList)
        self.fileManagerLayout.addSpacing(15)
        self.fileManagerLayout.addWidget(self.selectFile)
        self.fileManagerLayout.addWidget(self.syncButton)
        self.fileManagerLayout.addSpacing(30)
        self.fileManagerLayout.addWidget(self.peersListLabel, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addWidget(self.peersList)
        self.changeRoleLayout.addWidget(self.selectRole)
        self.changeRoleLayout.addWidget(self.changeRole)
        self.fileManagerLayout.addLayout(self.changeRoleLayout)
        self.fileManagerLayout.addSpacing(30)
        self.fileManagerLayout.addWidget(self.leaveButton)
        self.fileManagerLayout.addWidget(self.disconnectButton)

        self.restoreAllButton.clicked.connect(self.restoreAllHandler)
        self.createGroupButton.clicked.connect(self.createGroupHandler)
        self.resetCreateButton.clicked.connect(self.resetCreateHandler)
        self.activeGroupList.itemDoubleClicked.connect(self.activeGroupsDoubleClicked)
        self.otherGroupList.itemDoubleClicked.connect(self.otherGroupsDoubleClicked)
        self.selectFile.clicked.connect(self.addFile)
        self.changeRole.clicked.connect(self.changeRoleHandler)
        self.leaveButton.clicked.connect(self.leaveGroupHandler)
        self.disconnectButton.clicked.connect(self.disconnectGroupHandler)
        self.joinOrRestoreButton.clicked.connect(self.joinOrRestoreHandler)

        self.signals.refresh.connect(self.refreshGUI)

        success = peerInitialization()

        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))
        self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        self.activeGroupList.setToolTip(firstTip)
        self.otherGroupList.setToolTip(secondTip)

        self.loadInititalGroupInfo()

        self.show()

        if not success:
            """Create dialog box in order to set server coordinates"""
            ok = False
            while not ok:
                coordinates, ok = QInputDialog.getText(self, 'Server coordinates',
                                                       'Enter Server IP Address and Server Port\nUse the format: serverIP:ServerPort')

            peerCore.setServerCoordinates(coordinates)
            self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        peerCore.retrieveGroups()
        self.fillGroupManager()

        reply = QMessageBox.question(self, 'Message', "Do you want to restore last session groups?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.restoreAllHandler()

        peerCore.startSync(self.signals)
        
    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            peerCore.disconnectPeer()
            event.accept()
        else:
            event.ignore()

    def loadInititalGroupInfo(self):
        self.fileManagerLabel1.setText(firstTip)
        self.fileManagerLabel2.setText(secondTip)
        self.hideFileManager()

    def hideFileManager(self):

        self.joinOrRestoreButton.hide()
        self.fileListLabel.hide()
        self.fileList.hide()
        self.selectFile.hide()
        self.syncButton.hide()
        self.peersListLabel.hide()
        self.peersList.hide()
        self.selectRole.hide()
        self.changeRole.hide()
        self.leaveButton.hide()
        self.disconnectButton.hide()

    def fillGroupManager(self):

        self.activeGroupList.clear()
        self.otherGroupList.clear()

        """This function update groups list for the peer, retrieving information from the server"""     

        for group in peerCore.activeGroupsList.values():
            item = QListWidgetItem(group["name"])
            item.setTextAlignment(Qt.AlignHCenter)
            self.activeGroupList.addItem(item)

        for group in peerCore.restoreGroupsList.values():
            item = QListWidgetItem(group["name"])
            item.setTextAlignment(Qt.AlignHCenter)
            self.otherGroupList.addItem(item)

        for group in peerCore.otherGroupsList.values():
            item = QListWidgetItem(group["name"])
            item.setTextAlignment(Qt.AlignHCenter)
            self.otherGroupList.addItem(item)
            

    def updatePeersList(self, groupName):

        if peerCore.retrievePeers(groupName, selectAll=True):
            self.peersList.clear()
            for peer in peerCore.activeGroupsList[groupName]["peersList"]:
                status = "Active" if peer["active"] else "NotActive"
                self.peersList.addItem(peer["peerID"] + "\t" + status + "\t\t" + peer["role"])
        else:
            QMessageBox.about(self, "Error", "Error while retrieving list of peers!")    


    def restoreAllHandler(self):
        if len(peerCore.restoreGroupsList) != 0:
            reply = QMessageBox.question(self, 'Message', "Are you sure?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                peerCore.restoreAll()
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
                self.loadFileManager(groupName)
                QMessageBox.about(self, "OK", "Groups successfully created!")
            else:
                QMessageBox.about(self, "Error", "Group creation failed!")

    def resetCreateHandler(self):

        self.createGroupName.setText("Enter Group Name (single word name)")
        self.createTokenRW.clear()
        self.createTokenRWConfirm.clear()
        self.createTokenRO.clear()
        self.createTokenROConfirm.clear()



    def activeGroupsDoubleClicked(self, item):
        groupName = item.text().split()[0]
        self.loadFileManager(groupName)

    def loadFileManager(self, groupName):

        self.hideFileManager()

        groupInfo = peerCore.retrieveGroupInfo(groupName)

        if groupInfo["role"] != peerCore.activeGroupsList[groupName]["role"]:
            """Update the role of the peer in case of change"""
            peerCore.activeGroupsList[groupName]["role"] = groupInfo["role"]

        self.fileManagerLabel1.setText("FILE MANAGER GROUP {}".format(groupName))
        self.fileManagerLabel2.setText(statusLabel.format(
            groupInfo["role"], groupInfo["active"], groupInfo["total"]))
        
        self.fileListLabel.show()

        "Fills the files list"

        self.fileList.clear()
        self.fileList.show()

        if peerCore.activeGroupsList[groupName]["role"].upper() == "RW":
            self.selectFile.show()
            self.syncButton.show()

        if peerCore.activeGroupsList[groupName]["role"].upper() == "MASTER":
            self.selectFile.show()
            self.syncButton.show()
            self.peersListLabel.show()
            self.updatePeersList(groupName)
            self.peersList.show()
            self.selectRole.show()
            self.changeRole.show()

        self.leaveButton.show()
        self.disconnectButton.show()

    def otherGroupsDoubleClicked(self, item):

        groupName = item.text().split()[0]
        self.hideFileManager()
        self.joinOrRestoreButton.show()

        self.fileManagerLabel1.setText("GROUP {}".format(groupName))

        groupInfo = peerCore.retrieveGroupInfo(groupName)

        if groupInfo["role"] != "":

            if groupInfo["role"] != peerCore.restoreGroupsList[groupName]["role"]:
                """Update the role of the peer in case of change (by a master)"""
                peerCore.restoreGroupsList[groupName]["role"] = groupInfo["role"]

            self.fileManagerLabel2.setText(statusLabel.format(
                groupInfo["role"], groupInfo["active"], groupInfo["total"]))

            self.joinOrRestoreButton.setText("RESTORE")

        else:
            self.fileManagerLabel2.setText(statusLabel.format("/",groupInfo["active"], groupInfo["total"]))

            self.joinOrRestoreButton.setText("JOIN")



    def joinOrRestoreHandler(self):

        groupName = self.fileManagerLabel1.text().split()[1]

        if self.joinOrRestoreButton.text().upper() == "RESTORE":
            reply = QMessageBox.question(self, 'Message', "Are you sure you want to restore the group {} ?"
                                         .format(groupName),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                """call the restoreGroup function passing the groupName as parameter"""
                if peerCore.restoreGroup(groupName, delete=True):
                    self.fillGroupManager()
                    self.loadFileManager(groupName)
                else:
                    QMessageBox.about(self, "Error", "Something went wrong!")
        else:
            token, okPressed = QInputDialog.getText(self, "Get token", "Your token:", QLineEdit.Password, "")
            if okPressed and token != '':
                if peerCore.joinGroup(groupName, token):
                    self.fillGroupManager()
                    self.loadFileManager(groupName)
                else:
                    QMessageBox.about(self, "Error", "Wrong token!")



    def addFile(self):
        dlg = QFileDialog()
        filename = dlg.getOpenFileName(self, 'Add file to the group', 'c:\\')
        print(filename)
        self.fileList.addItem(filename[0])

    def changeRoleHandler(self):

        if self.peersList.currentItem() is not None:
            groupName = self.fileManagerLabel1.text().split()[3]
            targetPeerID = self.peersList.currentItem().text().split()[0]
            targetPeerStatus = self.peersList.currentItem().text().split()[1]
            action = self.selectRole.currentText()
            reply = QMessageBox.question(self, 'Message', "Are you sure you want to apply \"{}\" command to {}?"
                                         .format(action, targetPeerID),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                """make action string compatible with peerCore.changePeer()"""
                action = action.replace(" ", "_")
                if peerCore.changeRole(groupName, targetPeerID, action.upper()):
                    if action.upper() == "CHANGE_MASTER":
                        nrPeers = self.fileManagerLabel2.text().split()[4]
                        activeUsers = nrPeers.split("/")[0]
                        totalUsers = nrPeers.split("/")[1]
                        self.fileManagerLabel2.setText("ROLE: {} \t\t PEERS (ACTIVE/TOTAL): {}/{}"
                                                      .format(peerCore.activeGroupsList[groupName]["role"].upper(),
                                                              activeUsers, totalUsers))
                        self.peersListLabel.hide()
                        self.peersList.hide()
                        self.selectRole.hide()
                        self.changeRole.hide()
                        self.fillGroupManager()
                    else:
                        self.updatePeersList(groupName)
                    #if the targetPeer is active send it a message in order to make it able to refresh the window
                    if targetPeerStatus == "ACTIVE":
                        pass
                else:
                    QMessageBox.about(self, "Error", "Something went wrong!")
        else:
            QMessageBox.about(self, "Error", "You must select a peer from the list")

    def leaveGroupHandler(self):
        groupName = self.fileManagerLabel1.text().split()[3]
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to leave the group {} ?"
                                     .format(groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the leaveGroup function passing the groupName as parameter"""
            if peerCore.leaveGroup(groupName):
                self.fillGroupManager()
                self.loadInititalGroupInfo()
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")


    def disconnectGroupHandler(self):
        groupName = self.fileManagerLabel1.text().split()[3]
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to disconnect from the group {} ?"
                                     .format(groupName),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the disconnectGroup function passing the groupName as parameter"""
            if peerCore.disconnectGroup(groupName):
                self.fillGroupManager()
                self.loadInititalGroupInfo()
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")

    def refreshGUI(self, message):
        modMessage = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " >>> " + message
        self.actionsList.addItem(modMessage)
        self.actionsList.sortItems(order=Qt.DescendingOrder)
        QMessageBox.about(self, "Notification", message)


def peerInitialization():
    peerCore.setPeerID()
    found = peerCore.findServer()
    if found:
        return True
    else:
        return False


if __name__ == '__main__':
    app = QApplication([])
    darkgray_stylesheet = qdarkgraystyle.load_stylesheet()
    app.setStyleSheet(darkgray_stylesheet)
    window = myP2PSyncCloud()
    sys.exit(app.exec_())