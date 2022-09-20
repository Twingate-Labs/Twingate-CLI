
def checkStringAsBool(aString):
    if aString.lower() == "false":
        return True, False
    if aString.lower() == "true":
        return True, True
    return False,False