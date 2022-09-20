import json
import pandas as pd
import logging
import GenericTransformers

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id','name','hasStatusNotificationsEnabled']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'connectorUpdate',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id', 'name','lastHeartbeatAt','hasStatusNotificationsEnabled','state','remoteNetwork.id','remoteNetwork.name']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'connector',columns)

def GetListAsCsv(jsonResults):
    columns = ['id', 'name','state','lastHeartbeatAt','hasStatusNotificationsEnabled']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetGenTokensAsCsv(jsonResults):
    columns = ['ok', 'error','connectorTokens.accessToken','connectorTokens.refreshToken']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'connectorGenerateTokens',columns)
