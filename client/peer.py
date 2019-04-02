"""Client of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import socket
import time
import uuid
#import os

configurationFile = "conf.txt"
peerID = None
serverIP =None
serverPort = None

def createSocket(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    return s


def closeSocket(sock):
    # close the connection sock
    message = "BYE"
    sock.send(message.encode('ascii'))

    data = sock.recv(1024)
    #print('Received from the server :', str(data.decode('ascii')))
    # sleep one seconds
    time.sleep(0.1)
    sock.close()

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


def retrieveGroupsList(previous):
    if previous:
        tmp = "PREVIOUS"
    else:
        tmp = "OTHER"

    s = handshake()

    message = "SEND {} GROUPS LIST".format(tmp)
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


def restoreGroupWrapper():

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

def startSync():

    """create a server thread that listens on the port X"""
    #createServer

    s = handshake()

    message = "HERE {} {}".format(ipAddress, portNumber)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


if __name__ == '__main__':
    """main function, handles the configuration and the access to different groups"""

    print("Welcome to myLocalP2PCloud")

    print("Retrieving configuration..")
    try:
        file = open(configurationFile, 'r')
        configuration = file.readline().split()
        serverIP = configuration[0]
        serverPort = int(configuration[1])
    except FileNotFoundError:
        print("No configuration found")
        serverIP = input("Insert server IP:")
        serverPort = input("Insert server port:")
        """"save configuration on the file"""
        file = open(configurationFile, 'w')
        file.write("{} {}".format(serverIP, serverPort))
    file.close()

    """peer unique Identifier obtained from the MAC address of the machine"""
    macAddress = uuid.getnode()
    #peerID = int(time.ctime(os.path.getctime(configurationFile))) & macAddress
    peerID = macAddress

    """"Let the user restores previous synchronization groups"""
    restoreGroupWrapper()

    """Let the user joins new synchronization groups"""
    joinGroupWrapper()

    createGroupWrapper()

    print("Sync happens here...")

    """choose a port number available"""
    """here the peer has to communicate to the server on which port number its server function will run"""
    startSync()
