"""utilities functions script"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""

def createGroupDict(groupInfo):
    """"Initialize a dictionary used to store group information.
    Initial value are passed through a list"""
    groupDict = dict()
    groupDict["name"] = groupInfo[0]
    groupDict["tokenRW"] = groupInfo[1]
    groupDict["tokenRO"] = groupInfo[2]
    groupDict["total"] = int(groupInfo[3])
    groupDict["active"] = int(groupInfo[4])
    groupDict["peers"] = dict()
    return groupDict

def changeGroupInfo(group, role):
    """"This function return a group dictionary without the token fields and without the list of peers,
    but eventually adding the role of the peer in the group (if any)"""
    modGroup = dict()
    modGroup["name"] = group["name"]
    modGroup["total"] = group["total"]
    modGroup["active"] = group["active"]
    modGroup["role"] = role
    return modGroup