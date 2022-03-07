import json
import pandas as pd

def GetListAsCsv(jsonResults):

    DeviceList = jsonResults['data']['connectors']['edges']
    dfItem = pd.json_normalize(DeviceList)
    return dfItem
