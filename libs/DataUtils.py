import os
import random
import uuid

DATAFILEPATH = "./data/"
TOKENFILE = os.path.join(DATAFILEPATH, ".token_")
URLFILE = os.path.join(DATAFILEPATH, ".tenant_")

Animals = ['Dog','Eel','Cat','Bat','Cow','Elk','Fox','Ape','Boa','Yak','Fly']
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

def StoreTenant(tenant,sessionname):
    CheckAndCreateDataFolderIfNeeded()
    SessionFileName = URLFILE+sessionname
    deleteAFile(SessionFileName)
    text_file = open(SessionFileName, "w+")
    text_file.write(tenant)
    text_file.close()

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
    try:
        text_file = open(SessionFileName, "r")
        tenant = text_file.read()
        fullurl = "https://"+tenant+".twingate.com/api/graphql/"
        text_file.close()
        return fullurl,tenant
    except:
        print("Cannot get Tenant: Session ["+sessionname+"] does not exist.")
        exit(1)

def GetAuthToken(tenant,sessionname):
    SessionFileName = TOKENFILE+sessionname
    try:
        text_file = open(SessionFileName, "rb")
        token = text_file.read()
        detoken = decode(token,tenant)
        text_file.close()
        return detoken
    except:
        print("Cannot get Token: Session does not exist: "+sessionname)
        exit(1)

def RandomSessionNameGenerator():
    return random.choice(Colors)+random.choice(Animals)

def encode(cleartext,key):
    StubStr = uuid.uuid4().hex
    StringToEnc = StubStr+cleartext
    reps = (len(StringToEnc)-1)//len(key) +1
    a1 = StringToEnc.encode('utf-8')
    key = (key * reps)[:len(StringToEnc)].encode('utf-8')
    cipher = bytes([i1^i2 for (i1,i2) in zip(a1,key)])
    return cipher
    #return cleartext

def decode(cipher,key):
    reps = (len(cipher)-1)//len(key) +1
    key = (key * reps)[:len(cipher)].encode('utf-8')
    clear = bytes([i1^i2 for (i1,i2) in zip(cipher,key)])
    clearStr = clear.decode('utf-8')[32:]
    #print(clearStr)
    return clearStr
    #return cipher
