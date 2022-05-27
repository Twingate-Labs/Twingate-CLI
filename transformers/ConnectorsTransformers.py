import json
import pandas as pd
from pandas.io.json import json_normalize

def GetListAsCsv(jsonResults):

    DeviceList = jsonResults['data']['connectors']['edges']
    dfItem = json_normalize(DeviceList)
    return dfItem
