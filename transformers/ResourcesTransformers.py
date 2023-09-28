import json
import pandas as pd
import logging
import GenericTransformers

def GetShowAsCsv(jsonResults):
    columns = ['id','name','isActive','remoteNetwork.id','address.type','address.value','protocols.allowIcmp',
    'protocols.tcp.policy','protocols.udp.policy','isVisible','isBrowserShortcutEnabled']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'resource',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','name','isActive','remoteNetwork.id','address.type','address.value','securityPolicy','isVisible','isBrowserShortcutEnabled']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)

def GetCreateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceCreate',columns)

def GetDeleteAsCsv(jsonResults):
    columns = ['ok','error']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceDelete',columns)

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','remoteNetwork.id','remoteNetwork.name','address.type','address.value','alias']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceUpdate',columns)

def GetVisibilityUpdateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name','isVisible','isBrowserShortcutEnabled']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'resourceUpdate',columns)