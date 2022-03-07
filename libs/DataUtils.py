import os
import random

DATAFILEPATH = "./data/"
TOKENFILE = os.path.join(DATAFILEPATH, ".token_")
URLFILE = os.path.join(DATAFILEPATH, ".url_")

Animals = ['Dog','Mouse','Cat','Elephant','Cow','Eagle','Snake','Ape','Bull','Peacock','Fly']
Colors = ['Blue','Pink','Yellow','Green','Red','Orange','Purple','White','Black']

def CheckAndCreateDataFolderIfNeeded():
    if not os.path.exists(DATAFILEPATH):
        os.makedirs(DATAFILEPATH)

def listSessions():
    CheckAndCreateDataFolderIfNeeded()
    sessionlist = []
    try:
        for root, dirs, files in os.walk(DATAFILEPATH):
            for file in files:
                if("token" in file):
                    sessionlist.append(file.split("_")[1])
        return sessionlist,False
    except Exception as e:
        return e,True

def clearSessions():
    CheckAndCreateDataFolderIfNeeded()
    try:
        for root, dirs, files in os.walk(DATAFILEPATH):
            for file in files:
                os.remove(os.path.join(root, file))
        return False
    except:
        return True

def deleteAFile(filename):
    CheckAndCreateDataFolderIfNeeded()
    try:
        os.remove(filename)
    except:
        pass

def DeleteSessionFiles(sessionname):
    CheckAndCreateDataFolderIfNeeded()
    deleteAFile(URLFILE+sessionname)
    deleteAFile(TOKENFILE+sessionname)

def StoreUrl(url,sessionname):
    CheckAndCreateDataFolderIfNeeded()
    SessionFileName = URLFILE+sessionname
    deleteAFile(SessionFileName)
    text_file = open(SessionFileName, "w+")
    text_file.write(url)
    text_file.close()

def StoreAuthToken(token,sessionname):
    CheckAndCreateDataFolderIfNeeded()
    SessionFileName = TOKENFILE+sessionname
    deleteAFile(SessionFileName)
    text_file = open(SessionFileName, "w+")
    text_file.write(token)
    text_file.close()

def GetUrl(sessionname):
    SessionFileName = URLFILE+sessionname
    try:
        text_file = open(SessionFileName, "r")
        url = text_file.read()
        text_file.close()
        return url
    except:
        print("Cannot get URL: Session does not exist.")
        exit(1)

def GetAuthToken(sessionname):
    SessionFileName = TOKENFILE+sessionname
    try:
        text_file = open(SessionFileName, "r")
        token = text_file.read()
        text_file.close()
        return token
    except:
        print("Cannot get Token: Session does not exist: "+sessionname)
        exit(1)

def RandomSessionNameGenerator():
    return random.choice(Colors)+random.choice(Animals)
