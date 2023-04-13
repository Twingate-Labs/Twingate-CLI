import json
import pandas as pd
import logging
import GenericTransformers

def GetShowAsCsv(jsonResults):
    columns = ['id', 'firstName','lastName','email','role','state','groups']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'user',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','firstName','lastName','email','role','state','groups']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetUpdateAsCsv(jsonResults):
    columns = ['ok', 'error','id','firstName','lastName','email','role','state','groups']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'userRoleUpdate',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok', 'error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'userDelete',columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok', 'error','id','firstName','lastName','email','role','state']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'userCreate',columns)