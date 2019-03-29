"""Client of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

import hashlib
import socket
import time


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
    # sleep one seconds
    time.sleep(1)
    sock.close()


def retrieveGroupsList(s, previous):
    if previous:
        tmp = "PREVIOUS"
    else:
        tmp = "OTHER"

    message = "SEND {} GROUPS LIST".format(tmp)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    groupsList = eval(str(data.decode('ascii')))

    return groupsList


def restoreGroups(serverIP, serverPort):
    s = createSocket(serverIP, serverPort)

    print("Retrieving information about previous session..")
    previousGroupsList = retrieveGroupsList(s, previous=True)

    print("List of synchronization groups that you have already joined:")
    for group in previousGroupsList:
        print(group)

    while True:
        groupName = input("Write the name of the group you want to restore: ")

        message = "RESTORE Group: {}".format(groupName)
        print(message)
        s.send(message.encode('ascii'))

        data = s.recv(1024)
        print('Received from the server :', str(data.decode('ascii')))

        choice = input("Do you want to restore another group? (y/n)")

        if choice.upper() != "Y":
            break

    closeSocket(s)


def joinGroups(serverIP, serverPort):
    s = createSocket(serverIP, serverPort)

    print("Retrieving other groups list..")
    newGroupsList = retrieveGroupsList(s, previous=False)

    print("List of synchronization groups available:")
    for group in newGroupsList:
        print(group)

    while True:

        groupName = input("Write the name of the group you want to join: ")
        groupToken = input("Write the token of the group you want to access: ")

        encryptedToken = hashlib.md5(groupToken.encode())

        message = "JOIN Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
        # print(message)
        s.send(message.encode('ascii'))

        data = s.recv(1024)
        print('Received from the server :', str(data.decode('ascii')))

        choice = input("Do you want to join another group? (y/n)")

        if choice.upper() != "Y":
            break

    closeSocket(s)


def createGroups(serverIP, serverPort):
    s = createSocket(serverIP, serverPort)

    while True:

        groupName = input("Write the name of the group you want to create: ")
        groupTokenRW = input("Write the token for Reader&Writer of the group you want to create: ")
        groupTokenRO = input("Write the token for ReadOnly of the group you want to create: ")

        encryptedTokenRW = hashlib.md5(groupTokenRW.encode())
        encryptedTokenRO = hashlib.md5(groupTokenRO.encode())

        message = "CREATE Group: {} TokenRW: {} TokenRO: {}".format(groupName,
                                                                    encryptedTokenRW.hexdigest(),
                                                                    encryptedTokenRO.hexdigest())
        s.send(message.encode('ascii'))

        data = s.recv(1024)
        print('Received from the server :', str(data.decode('ascii')))

        choice = input("Do you want to create another group? (y/n)")

        if choice.upper() != "Y":
            break

    closeSocket(s)


if __name__ == '__main__':
    """main function, handles the configuration and the access to different groups"""

    print("Welcome to myLocalP2PCloud")

    print("Retrieving configuration..")
    try:
        file = open('conf.txt', 'r')
        configuration = file.readline().split()
        serverIP = configuration[0]
        serverPort = int(configuration[1])
    except FileNotFoundError:
        print("No configuration found")
        serverIP = input("Insert server IP:")
        serverPort = input("Insert server port:")
        """"save configuration on the file"""
        file = open('conf.txt', 'w')
        file.write("{} {}".format(serverIP, serverPort))
    file.close()

    """"Let the user restores previous synchronization groups"""
    #restoreGroups(serverIP, serverPort)

    """Let the user joins new synchronization groups"""
    #joinGroups(serverIP, serverPort)

    createGroups(serverIP, serverPort)
