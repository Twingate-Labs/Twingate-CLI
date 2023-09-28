import json
import pandas as pd
import logging
import GenericTransformers

def GetShowAsCsv(jsonResults):
    columns = ['id','name','keys','resources']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'serviceAccount',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','name','createdAt','updatedAt','keys','resources']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetAddOrRemoveResourcesAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','resources']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountUpdate',columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountCreate',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountDelete',columns)
