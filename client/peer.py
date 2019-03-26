import argparse
import hashlib
import socket
import time


def get_args():
    """
    Get command line args from the user.
    """
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to Central Index Server')
    parser.add_argument('-a', '--address',
                        default="127.0.0.1",
                        action='store',
                        help='Server IP address')
    parser.add_argument('-p', '--port',
                        type=int,
                        default=2010,
                        # required=True,
                        action='store',
                        help='Server Port Number')
    args = parser.parse_args()
    return args


def createSocket(host, port):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect to server on local computer
    s.connect((host, port))

    return s


def retrieveGroupList(serverAddress, serverPort):

    s = createSocket(serverAddress, serverPort)

    """"message you send to server
    message = "hello server"

    # message sent to server
    s.send(message.encode('ascii'))

    # message received from server
    data = s.recv(1024)

    # print the received message
    print('Received from the server :', str(data.decode('ascii')))"""

    message = "SEND GROUPS LIST"

    s.send(message.encode('ascii'))

    data = s.recv(1024)

    groupList = eval(str(data.decode('ascii')))
    print('Groups List :', groupList)

    groupName = input("Write the name of the group you want to access: ")
    groupToken = input("Write the token of the group you want to access: ")

    encryptedToken = hashlib.md5(groupToken.encode())

    message = "Group: {} Token: {}".format(groupName, encryptedToken.hexdigest())
    print(message)
    s.send(message.encode('ascii'))

    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))

    # close the connection

    message = "BYE"

    s.send(message.encode('ascii'))
    data = s.recv(1024)
    print('Received from the server :', str(data.decode('ascii')))
    # sleep one seconds
    time.sleep(1)
    s.close()


def joinGroup():
    pass


def restoreGroup():
    pass


def main():
    """main function, handles the menu"""

    args = get_args()
    serverIP = args.address
    serverPort = args.port

    print(serverIP)

    print("Welcome to myLocalP2PCloud")
    print()

    while True:

        print("Press 1 to rejoin a previous group")
        print("Press 2 to join a new group")
        choice = input("Choice: ")

        if choice == "1":
            print()
            restoreGroup()
            break

        elif choice == "2":
            print("Retrieving the groups list..")
            retrieveGroupList(serverIP, serverPort)
            joinGroup()
            break

        else:
            print("Wrong Input")
            # go back to the input phase


main()
