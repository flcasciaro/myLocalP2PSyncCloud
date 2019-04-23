"""Peer core code of myLocalP2PSyncCLoud"""

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

"""main data structures for the groups handling"""
activeGroupsList = {}
restoreGroupsList = {}
otherGroupsList = {}

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


def retrieveGroups(action):

    s = handshake()

    message = "SEND {} GROUPS".format(action.upper())
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

    for group in restoreGroupsList.values():
        restoreGroup(group["name"])




def joinGroup(groupName, token):

    s = handshake()

    encryptedToken = hashlib.md5(token.encode())

    message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    # print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


def createGroup(groupName, groupTokenRW, groupTokenRO):

    s = handshake()

    encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
    encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

    message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                encryptedTokenRW.hexdigest(),
                                                                encryptedTokenRO.hexdigest())
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)
    if str(data.decode('ascii')).split()[0] == "ERROR:":
        return False
    else:
        return True


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

def disconnectPeer():

    s = handshake()

    message = "DISCONNECT"
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


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