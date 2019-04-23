"""Peer GUI code of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import sys

from PyQt5.QtWidgets import *

import peerCore


class myP2PSyncCloud(QMainWindow):

    def __init__(self):
        super().__init__()
        """Window properties definition"""
        self.title = "myP2PSyncCloud"
        self.left = 300
        self.top = 50
        self.width = 500
        self.height = 500

        """Window main structure definition"""
        self.splitter = QSplitter()
        self.groupManager = QFrame()
        self.fileManager = QFrame()

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
        self.createGroupName = QLineEdit("Enter Group Name (single word name)")
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
        self.fileLabel = QLabel("FILE MANAGER")
        self.fileButton = QPushButton("SYNC")

        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.setCentralWidget(self.splitter)

        self.splitter.addWidget(self.groupManager)
        self.splitter.addWidget(self.fileManager)
        """self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 5)"""

        self.groupManager.setLineWidth(3)
        self.fileManager.setLineWidth(3)
        self.groupManager.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.fileManager.setFrameStyle(QFrame.Box | QFrame.Raised)

        self.groupManager.setLayout(self.groupManagerLayout)
        self.fileManager.setLayout(self.fileManagerLayout)

        self.groupManagerLayout.addWidget(self.peerLabel)
        self.groupManagerLayout.addWidget(self.serverLabel)
        self.groupManagerLayout.addSpacing(30)

        self.groupManagerLayout.addWidget(self.activeGroupLabel)
        self.groupManagerLayout.addWidget(self.activeGroupList)
        self.groupManagerLayout.addSpacing(30)
        self.groupManagerLayout.addWidget(self.otherGroupLabel)
        self.groupManagerLayout.addWidget(self.otherGroupList)
        self.groupManagerLayout.addWidget(self.restoreAllButton)
        self.groupManagerLayout.addSpacing(30)

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
        self.groupManagerLayout.addSpacing(30)

        self.fileManagerLayout.addWidget(self.fileLabel)
        self.fileManagerLayout.addWidget(self.fileButton)

        self.restoreAllButton.clicked.connect(self.restoreAllHandler)
        self.createGroupButton.clicked.connect(self.createGroupHandler)
        self.resetCreateButton.clicked.connect(self.resetCreateHandler)
        self.activeGroupList.itemDoubleClicked.connect(self.activeGroupsClicked)
        self.otherGroupList.itemDoubleClicked.connect(self.otherGroupsClicked)

        success = peerInitialization()

        self.peerLabel.setText("Personal peerID is {}".format(peerCore.peerID))
        self.serverLabel.setText("Connected to server at {}:{}".format(peerCore.serverIP, peerCore.serverPort))

        self.activeGroupList.setToolTip("Double click on a group in order to see files")
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

        peerCore.startSync()

        self.updateGroupsUI()

        reply = QMessageBox.question(self, 'Message', "Do you want to restore last session groups?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.restoreAllHandler()


    def restoreAllHandler(self):
        if len(peerCore.restoreGroupsList) != 0:
            peerCore.restoreAll()
            self.updateGroupsUI()
        else:
            QMessageBox.about(self, "Alert", "You don't have restorable groups")

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

        peerCore.activeGroupsList = peerCore.retrieveGroups(action="active")
        peerCore.restoreGroupsList = peerCore.retrieveGroups(action="previous")
        peerCore.otherGroupsList = peerCore.retrieveGroups(action="other")

        for group in peerCore.activeGroupsList.values():
            self.activeGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "\t"
                                         + str(group["total"]) + "\t" + group["role"])

        for group in peerCore.restoreGroupsList.values():
            self.otherGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "\t"
                                        + str(group["total"]) + "\t" + "JOINED" + "\t" + group["role"])

        for group in peerCore.otherGroupsList.values():
            self.otherGroupList.addItem(group["name"] + "\t" + str(group["active"]) + "\t"
                                        + str(group["total"]) + "\t" + "NOT JOINED")

    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure to quit?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            peerCore.disconnectPeer()
            event.accept()
        else:
            event.ignore()

    def activeGroupsClicked(self, item):
        pass

    def otherGroupsClicked(self, item):
        if item.text().split()[3] == "JOINED":
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


def peerInitialization():
    peerCore.setPeerID()
    found = peerCore.findServer()
    if found:
        return True
    else:
        return False



if __name__ == '__main__':
    app = QApplication([])
    ex = myP2PSyncCloud()
    sys.exit(app.exec_())
