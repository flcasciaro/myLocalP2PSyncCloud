"""Client of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""


import hashlib
import socket
import time


def createSocket(host, port):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect to server on local computer
    s.connect((host, port))

    return s


def closeSocket(sock):
    # close the connection sock
    message = "BYE"
    sock.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))
    # sleep one seconds
    time.sleep(1)
    sock.close()


def retrieveGroups(serverAddress, serverPort, previous):

    s = createSocket(serverAddress, serverPort)

    if previous:
        tmp = "PREVIOUS"
    else:
        tmp = "NEW"

    message = "SEND {} GROUPS LIST".format(tmp)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    groupList = eval(str(data.decode('ascii')))
    print('Groups List :', groupList)

    closeSocket(s)

    return groupList


def restoreGroup():
    closeSocket(s)


def retrieveGroupList(serverAddress, serverPort):

    s = createSocket(serverAddress, serverPort)

    message = "SEND NEW GROUPS LIST"
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    groupList = eval(str(data.decode('ascii')))
    print('Groups List :', groupList)

    closeSocket(s)

    return newGroupList


def joinGroup(serverAddress, serverPort, newGroupsList):

    s = createSocket(serverAddress, serverPort)

    groupName = input("Write the name of the group you want to access: ")
    groupToken = input("Write the token of the group you want to access: ")

    encryptedToken = hashlib.md5(groupToken.encode())

    message = "Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    closeSocket(s)


if __name__ == '__main__':
    """main function, handles the menu"""

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

    print("Retrieving information about previous session..")
    previousGroupsList = retrieveGroups(serverAddress, serverPort, previous=True)

    restoreGroup(previousGroupsList)

    print("Retrieving other groups list..")
    newGroupsList = retrieveGroups(serverIP, serverPort, previous=False)

    joinGroup(serverIP, serverPort, newGroupsList)

