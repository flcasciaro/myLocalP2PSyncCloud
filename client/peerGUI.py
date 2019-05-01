"""Peer GUI code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import datetime
import sys

import qdarkgraystyle
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import mySignals
import peerCore


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
        self.activeGroupInfo = QLabel("Name\t\tActive/Total\t\tRole")
        self.activeGroupList = QListWidget()
        self.otherGroupLabel = QLabel("List of OTHER groups")
        self.otherGroupInfo = QLabel("Name\t\tActive/Total\t\tStatus")
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
        self.fileManagerLabel = QLabel("Double click on an active group in order to access the file manager")
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
        self.horizontalSplitter.addWidget(self.fileManager)

        self.verticalSplitter.addWidget(self.horizontalSplitter)
        self.verticalSplitter.addWidget(self.actionsList)

        self.groupManager.setLayout(self.groupManagerLayout)
        self.fileManager.setLayout(self.fileManagerLayout)

        self.groupManagerLayout.addWidget(self.peerLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.serverLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addSpacing(25)

        self.groupManagerLayout.addWidget(self.activeGroupLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.activeGroupInfo)
        self.groupManagerLayout.addWidget(self.activeGroupList)
        self.groupManagerLayout.addSpacing(15)
        self.groupManagerLayout.addWidget(self.otherGroupLabel, alignment=Qt.AlignCenter)
        self.groupManagerLayout.addWidget(self.otherGroupInfo)
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

        self.hideFileManager()

        self.fileManagerLayout.addWidget(self.fileManagerLabel, alignment=Qt.AlignCenter)
        self.fileManagerLayout.addSpacing(30)
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
        self.activeGroupList.itemDoubleClicked.connect(self.activeGroupsClicked)
        self.otherGroupList.itemDoubleClicked.connect(self.otherGroupsClicked)
        self.selectFile.clicked.connect(self.addFile)
        self.changeRole.clicked.connect(self.changeRoleHandler)
        self.leaveButton.clicked.connect(self.leaveGroupHandler)
        self.disconnectButton.clicked.connect(self.disconnectGroupHandler)

        self.signals.refresh.connect(self.refreshGUI)

        success = peerInitialization()

        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))
        self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        self.activeGroupList.setToolTip("Double click on a group in order to see manage it")
        self.otherGroupList.setToolTip("Double click on a group in order to join or restore it")

        self.show()

        if not success:
            """Create dialog box in order to set server coordinates"""
            ok = False
            while not ok:
                coordinates, ok = QInputDialog.getText(self, 'Server coordinates',
                                                       'Enter Server IP Address and Server Port\nUse the format: serverIP:ServerPort')

            peerCore.setServerCoordinates(coordinates)
            self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        peerCore.startSync(self.signals)

        self.updateGroupsUI()

        reply = QMessageBox.question(self, 'Message', "Do you want to restore last session groups?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.restoreAllHandler()


    def restoreAllHandler(self):
        if len(peerCore.restoreGroupsList) != 0:
            reply = QMessageBox.question(self, 'Message', "Are you sure?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                peerCore.restoreAll()
                self.updateGroupsUI()
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
        elif len(groupTokenRW) == 0 or len(groupTokenRO) == 0 or groupTokenRW != groupTokenRWConfirm or groupTokenRO != groupTokenROConfirm:
            QMessageBox.about(self, "Error", "Invalid tokens!")
        else:
            if peerCore.createGroup(groupName, groupTokenRW, groupTokenRO):
                self.updateGroupsUI()
                self.resetCreateHandler()
                QMessageBox.about(self, "OK", "Groups successfully created!")
            else:
                QMessageBox.about(self, "Error", "Group creation failed!")

    def resetCreateHandler(self):

        self.createGroupName.setText("Enter Group Name (single word name)")
        self.createTokenRW.clear()
        self.createTokenRWConfirm.clear()
        self.createTokenRO.clear()
        self.createTokenROConfirm.clear()


    """This function update groups list for the peer, retrieving information from the server"""
    def updateGroupsUI(self):

        self.activeGroupList.clear()
        self.otherGroupList.clear()

        peerCore.retrieveGroups()

        for group in peerCore.activeGroupsList.values():
            self.activeGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "/"
                                         + str(group["total"]) + "\t" + group["role"])

        for group in peerCore.restoreGroupsList.values():
            self.otherGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "/"
                                        + str(group["total"]) + "\t" + "JOINED" + " AS " + group["role"])

        for group in peerCore.otherGroupsList.values():
            self.otherGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "/"
                                        + str(group["total"]) + "\t" + "NOT JOINED")

    def hideFileManager(self):

        self.fileManagerLabel.setText("Double click on an active group in order to access the file manager")
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

    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure you want to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            peerCore.disconnectPeer()
            event.accept()
        else:
            event.ignore()

    def updatePeersList(self, groupName):

        if peerCore.retrievePeers(groupName, selectAll=True):
            self.peersList.clear()
            for peer in peerCore.activeGroupsList[groupName]["peersList"]:
                status = "Active" if peer["active"] else "NotActive"
                self.peersList.addItem(peer["peerID"] + "\t" + status + "\t" + peer["role"])
        else:
            QMessageBox.about(self, "Error", "Error while retrieving list of peers!")

    def activeGroupsClicked(self, item):

        self.hideFileManager()

        groupName = item.text().split()[0]

        self.fileManagerLabel.setText("GROUP {} FILE MANAGER\tROLE: {}".format(groupName,
                                        peerCore.activeGroupsList[groupName]["role"].upper()))
        self.fileListLabel.show()
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


    def otherGroupsClicked(self, item):
        if item.text().split()[2] == "JOINED":
            reply = QMessageBox.question(self, 'Message', "Are you sure you want to restore the group {} ?"
                                         .format(item.text().split()[0]),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                """call the restoreGroup function passing the groupName as parameter"""
                peerCore.restoreGroup(item.text().split()[0])
                self.updateGroupsUI()
        else:
            token, okPressed = QInputDialog.getText(self, "Get token", "Your token:", QLineEdit.Password, "")
            if okPressed and token != '':
                peerCore.joinGroup(item.text().split()[0], token)
                self.updateGroupsUI()

    def addFile(self):
        dlg = QFileDialog()
        filename = dlg.getOpenFileName(self, 'Add file to the group', 'c:\\')
        print(filename)
        self.fileList.addItem(filename[0])

    def changeRoleHandler(self):

        if self.peersList.currentItem() is not None:
            groupName = self.fileManagerLabel.text().split()[1]
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
                        self.fileManagerLabel.setText("GROUP {} FILE MANAGER\tROLE: {}"
                                                      .format(groupName,
                                                              peerCore.activeGroupsList[groupName]["role"].upper()))
                        self.peersListLabel.hide()
                        self.peersList.hide()
                        self.selectRole.hide()
                        self.changeRole.hide()
                        self.updateGroupsUI()
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
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to leave the group {} ?"
                                     .format(self.fileManagerLabel.text().split()[1]),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the leaveGroup function passing the groupName as parameter"""
            if peerCore.leaveGroup(self.fileManagerLabel.text().split()[1]):
                self.hideFileManager()
                self.updateGroupsUI()
            else:
                QMessageBox.about(self, "Error", "Something went wrong!")


    def disconnectGroupHandler(self):
        reply = QMessageBox.question(self, 'Message', "Are you sure you want to disconnect from the group {} ?"
                                     .format(self.fileManagerLabel.text().split()[1]),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            """call the disconnectGroup function passing the groupName as parameter"""
            if peerCore.disconnectGroup(self.fileManagerLabel.text().split()[1]):
                self.hideFileManager()
                self.updateGroupsUI()
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