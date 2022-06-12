import json
import pandas as pd
import logging
import GenericTransformers


def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','token','id','name','expiresAt','status']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountKeyCreate',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id','name','expiresAt','revokedAt','status']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'serviceAccountKey',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountKeyDelete',columns)

def GetRevokeAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'serviceAccountKeyRevoke',columns)
