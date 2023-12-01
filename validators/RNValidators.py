import json
import pandas as pd

REMOTENETWORKLOCATIONS = ["AWS","AZURE","GOOGLE_CLOUD","ON_PREMISE","OTHER"]
def ValidateRNLocation(location):
    if location.upper() not in REMOTENETWORKLOCATIONS:
        return False,"Wrong Value, only the following options are valid: "+str(REMOTENETWORKLOCATIONS)
    return True,location.upper()