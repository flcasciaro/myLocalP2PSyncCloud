"""Client of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import socket
import time
import uuid
#import os

configurationFile = "conf.txt"
peerID = None
serverIP = None
serverPort = None

def setPeerID():
    global peerID
    """peer unique Identifier obtained from the MAC address of the machine"""
    macAddress = uuid.getnode()
    # peerID = int(time.ctime(os.path.getctime(configurationFile))) & macAddress
    peerID = macAddress

def findServer():
    global serverIP, serverPort
    try:
        file = open(configurationFile, 'r')
        configuration = file.readline().split()
        serverIP = configuration[0]
        serverPort = int(configuration[1])
    except FileNotFoundError:
        return False
    file.close()
    return True

def setServerCoordinates(coordinates):
    global serverIP, serverPort
    serverIP = coordinates.split(":")[0]
    serverPort = coordinates.split(":")[1]

def createSocket(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    return s

def closeSocket(sock):
    # close the connection sock
    message = "BYE"
    sock.send(message.encode('ascii'))

    data = sock.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))
    if data.decode('ascii').rstrip() == "BYE PEER":
        time.sleep(0.1)
        sock.close()
    else:
        serverError()

def serverError():
    print("UNEXPECTED ANSWER OF THE SERVER")
    exit(-1)

def serverUnreachable():
    print("UNABLE TO REACH THE SERVER")
    exit(-1)


def handshake():

    s = createSocket(serverIP, serverPort)

    message = "I'M {}".format(peerID)
    s.send(message.encode('ascii'))

    answer = s.recv(1024).decode('ascii').strip()

    if answer != "HELLO {}".format(peerID):
        print ("Unable to perform the initial handshake with the server")
        return None

    print("Connection with server established")
    return s


def retrieveGroupsList(action):

    s = handshake()

    message = "SEND {} GROUPS LIST".format(action.upper())
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    groupsList = eval(str(data.decode('ascii')))

    closeSocket(s)

    return groupsList

def restoreGroup(groupName):

    s = handshake()

    message = "RESTORE Group: {}".format(groupName)
    print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


def restoreAll():

    print("Retrieving information about previous sessions..")
    previousGroupsList = retrieveGroupsList(previous=True)

    print("List of synchronization groups that you have already joined:")
    for group in previousGroupsList:
        print("GroupName: {} \tActive members: {} \tTotal members: {}"
              .format(group["name"], group["active"], group["total"]))

    choice = input("Do you want to restore all the synchronization groups? (y/n): ")

    if choice.upper() == 'Y':
        for group in previousGroupsList:
            restoreGroup(group["name"])

    else:
        choice = input("Do you want to restore a synchronization session with one of these groups? (y/n): ")

        if choice.upper() == 'Y':
            while True:
                groupName = input("Write the name of the group you want to restore: ")

                restoreGroup(groupName)

                choice = input("Do you want to restore another group? (y/n): ")

                if choice.upper() != "Y":
                    break

def joinGroup(groupName, encryptedToken):

    s = handshake()

    message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    # print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

def joinGroupWrapper():

    print("Retrieving other groups list..")
    newGroupsList = retrieveGroupsList(previous=False)

    print("List of synchronization groups available (never joined):")
    for group in newGroupsList:
        print("GroupName: {} \tActive members: {} \tTotal members: {}"
              .format(group["name"], group["active"], group["total"]))

    choice = input("Do you want to join one of these groups? (y/n): ")

    if choice.upper() == 'Y':
        while True:

            groupName = input("Write the name of the group you want to join: ")
            groupToken = input("Write the token of the group you want to access: ")

            encryptedToken = hashlib.md5(groupToken.encode())

            joinGroup(groupName, encryptedToken)

            choice = input("Do you want to join another group? (y/n): ")

            if choice.upper() != "Y":
                break

def createGroup(groupName, encryptedTokenRW, encryptedTokenRO):

    s = handshake()

    message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

def createGroupWrapper():

    choice = input("Do you want to create a new synchronization group? (y/n): ")

    if choice.upper() == 'Y':

        while True:

            groupName = input("Write the name of the group you want to create: ")
            groupTokenRW = input("Write the token for Reader&Writer of the group you want to create: ")
            groupTokenRO = input("Write the token for ReadOnly of the group you want to create: ")

            encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
            encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

            createGroup(groupName, encryptedTokenRW, encryptedTokenRO)

            choice = input("Do you want to create another group? (y/n): ")

            if choice.upper() != "Y":
                break


def roleManagement():
    """this function addresses the management of the master and the management of roles by the master"""
    s = handshake()

    while True:
        action = input("Select an action: CHANGE_MASTER - ADD_MASTER - TO_RW - TO_RO: ")
        if action.upper() == "CHANGE_MASTER" or action.upper() == "ADD_MASTER"\
        or action.upper() == "TO_RW" or action.upper() == "TO_RO":
            break
        else:
            print("Invalid action")

    newMasterID = input("Enter the peerID of the peer to which you want to change role: ")
    groupName = input("Enter the name of the group: ")

    message = "ROLE {} {} GROUP {}".format(action.upper(), newMasterID, groupName)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)

def retrievePeers(groupName, all):

    s = handshake()

    if all:
        tmp = "ALL"
    else:
        tmp = "ACTIVE"

    message = "PEERS {} {} ".format(groupName, tmp)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    if data.decode('ascii').split()[0] == "ERROR":
        print('Received from the server :', str(data.decode('ascii')))
        peersList = None
    else:
        peersList = eval(str(data.decode('ascii')))
        print(peersList)

    closeSocket(s)
    return peersList

def startSync():

    """create a server thread that listens on the port X"""
    #createServer

    s = handshake()

    #retrieve internal IP address
    myIP = socket.gethostbyname(socket.gethostname())
    print(myIP)

    portNumber = 10000

    message = "HERE {} {}".format(myIP, portNumber)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)