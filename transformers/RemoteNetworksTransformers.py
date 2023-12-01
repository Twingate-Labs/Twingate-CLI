import json
import pandas as pd
import logging
import GenericTransformers

def GetShowAsCsv(jsonResults):
    columns = ['id','name','isActive','resources','connectors']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'remoteNetwork',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','name','isActive','resources','connectors']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'remoteNetworkCreate',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'remoteNetworkDelete',columns)
