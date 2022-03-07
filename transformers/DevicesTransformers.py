import json
import pandas as pd

def GetListAsCsv(jsonResults):

    DeviceList = jsonResults['data']['devices']['edges']
    dfItem = pd.json_normalize(DeviceList)
    return dfItem
