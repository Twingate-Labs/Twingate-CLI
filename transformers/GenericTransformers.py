import json
import pandas as pd

def GetListAsCsv(jsonResults,ObjectName):

    GenList = jsonResults['data'][ObjectName]['edges']
    dfItem = pd.json_normalize(GenList)
    return dfItem

def GetShowAsCsv(jsonResults,ObjectName):

    GenList = jsonResults['data'][ObjectName]
    dfItem = pd.json_normalize(GenList)
    return dfItem
