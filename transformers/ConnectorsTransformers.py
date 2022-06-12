import json
import pandas as pd
import logging
import GenericTransformers

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id','name']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'connectorUpdate',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id', 'name','lastHeartbeatAt','state','remoteNetwork.id','remoteNetwork.name']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'connector',columns)

def GetListAsCsv(jsonResults):
    columns = ['id', 'name','state','lastHeartbeatAt']
    return GenericTransformers.GetListAsCsvNoNesting(jsonResults,'connectors',columns)