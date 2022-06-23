import json
import pandas as pd
import logging
import GenericTransformers

def GetAddOrRemoveResourcesAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','resources']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'groupUpdate',columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','resources','users']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'groupCreate',columns)

def GetAddOrRemoveUsersAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','users']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'groupUpdate',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id','name','isActive','type','users','resources']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'group',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','name','isActive','type','users','resources']
    #return GenericTransformers.GetListAsCsvNoNesting(jsonResults,'groups',columns)
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'groupDelete',columns)

