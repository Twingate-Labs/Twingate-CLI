import os
import random
import uuid
import logging
from os.path import exists

DATAFILEPATH = "./data/"
TOKENFILE = os.path.join(DATAFILEPATH, ".token_")
URLFILE = os.path.join(DATAFILEPATH, ".tenant_")
STGFILE = os.path.join(DATAFILEPATH, ".stg_")

Animals = ['Dog','Eel','Cat','Bat','Cow','Elk','Fox','Ape','Boa','Yak','Fly']
Colors = ['Blue','Pink','Yellow','Green','Red','Orange','Purple','White','Black']

def CheckAndCreateDataFolderIfNeeded():
    if not os.path.exists(DATAFILEPATH):
        logging.debug("Creating Folder to Store Token and Tenant Name.")
        os.makedirs(DATAFILEPATH)
        logging.debug("Created:"+str(DATAFILEPATH))

def listSessions():
    CheckAndCreateDataFolderIfNeeded()
    sessionlist = []
    try:
        logging.debug("Looking for Existing Sessions.")
        for root, dirs, files in os.walk(DATAFILEPATH):
            for file in files:
                logging.debug("Scanning: "+str(file))
                if("token" in file):
                    SessionName = file.split("_")[1]
                    sessionlist.append(SessionName)
                    logging.debug("Session Added for: "+str(SessionName))
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

def StoreTenant(tenant,sessionname):
    CheckAndCreateDataFolderIfNeeded()
    SessionFileName = URLFILE+sessionname
    deleteAFile(SessionFileName)
    text_file = open(SessionFileName, "w+")
    text_file.write(tenant)
    text_file.close()

def IsStagingFlagPresent(sessionname):
    StgFlag = STGFILE+sessionname
    if exists(StgFlag):
        return True
    else:
        return False

def StoreAuthToken(token,tenant,sessionname):
    CheckAndCreateDataFolderIfNeeded()
    SessionFileName = TOKENFILE+sessionname
    deleteAFile(SessionFileName)
    text_file = open(SessionFileName, "wb+")
    #encodedtoken = encode(token,tenant).decode('utf-8')
    text_file.write(encode(token,tenant))

    text_file.close()

def GetUrl(sessionname):
    SessionFileName = URLFILE+sessionname
    logging.debug("Getting URL From Session File: "+str(SessionFileName))
    try:
        text_file = open(SessionFileName, "r")
        tenant = text_file.read()
        logging.debug("Tenant Name: "+str(tenant))
        fullprodurl = "https://"+tenant+".twingate.com/api/graphql/"
        fullstagingurl="https://"+tenant+".stg.opstg.com/api/graphql/"
        if IsStagingFlagPresent(sessionname):
            fullurl=fullstagingurl
        else:
            fullurl=fullprodurl
            
        logging.debug("Full Url: "+str(fullurl))
        text_file.close()
        return fullurl,tenant
    except:
        print("Cannot get Tenant: Session ["+sessionname+"] does not exist.")
        exit(1)

def GetAuthToken(tenant,sessionname):
    SessionFileName = TOKENFILE+sessionname
    logging.debug("Getting Token From Session File: "+str(SessionFileName))
    try:
        text_file = open(SessionFileName, "rb")
        token = text_file.read()
        logging.debug("Encrypted Token: "+str(token))
        detoken = decode(token,tenant)
        logging.debug("Decrypted Token: "+str(detoken))
        text_file.close()
        return detoken
    except:
        print("Cannot get Token: Session does not exist: "+sessionname)
        exit(1)

def RandomSessionNameGenerator():
    SessionName = random.choice(Colors)+random.choice(Animals)
    logging.debug("Session Name Generated: "+str(SessionName))
    return SessionName

def encode(cleartext,key):
    StubStr = uuid.uuid4().hex
    StringToEnc = StubStr+cleartext
    reps = (len(StringToEnc)-1)//len(key) +1
    a1 = StringToEnc.encode('utf-8')
    key = (key * reps)[:len(StringToEnc)].encode('utf-8')
    cipher = bytes([i1^i2 for (i1,i2) in zip(a1,key)])
    return cipher

def decode(cipher,key):
    reps = (len(cipher)-1)//len(key) +1
    key = (key * reps)[:len(cipher)].encode('utf-8')
    clear = bytes([i1^i2 for (i1,i2) in zip(cipher,key)])
    clearStr = clear.decode('utf-8')[32:]
    return clearStr
