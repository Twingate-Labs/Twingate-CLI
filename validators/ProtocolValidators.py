import json
import pandas as pd

POLICYOPTIONS = ["ALLOW_ALL","RESTRICTED"]
def ValidatePolicy(Policy):
    if Policy.upper() not in POLICYOPTIONS:
        return False,"Wrong Value, only the following options are valid: "+str(POLICYOPTIONS)
    return True,Policy.upper()

def ValidateRange(Ranges):
    # "ports": [{"start":22,"end":22},{"start":443,"end":446},{"start":556,"end":778}]
    FinalRanges = []
    ProcessedRanges = Ranges.replace(";",",").replace(":",",").replace("-",",").replace(",,",",")
    ProcessedRanges = json.loads(ProcessedRanges)
    if ProcessedRanges == "[]" or ProcessedRanges == "[[]]" :
        return True,[]

    if not str(ProcessedRanges).startswith("[") or not str(ProcessedRanges).endswith("]"):
        return False,"Not a valid list."

    for aRange in ProcessedRanges:

        if len(aRange) != 2:
            return False,"Wrong Format, All Ranges should contain 2 port values."
        for port in aRange:
            if int(port) < 1 or int(port) > 65535:
                return False,"Wrong Format, ports should be between 0 and 66535."
        if int(aRange[0])> int(aRange[1]):
                return False,"Wrong Format, start port should be lower or equal to end port."

        FinalRanges.append({"start":int(aRange[0]),"end":int(aRange[1])})
    return True,FinalRanges

def ValidateRangeWithPolicy(Range,Policy):
    if Policy.upper() == POLICYOPTIONS[0] and str(Range) != "[]":
        return False,POLICYOPTIONS[0]+" Policy Option is not compatible with a non-empty port range: "+str(Range)+". Please use "+POLICYOPTIONS[1]+" instead."
    else:
        return True,None
