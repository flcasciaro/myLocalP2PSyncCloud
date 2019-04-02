"""utilities functions script"""

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

def hideGroupInfo(group):
    """"This function return a group dictionary without the token fields and without the list of peers"""
    modGroup = dict()
    modGroup["name"] = group["name"]
    modGroup["total"] = group["total"]
    modGroup["active"] = group["active"]
    return modGroup