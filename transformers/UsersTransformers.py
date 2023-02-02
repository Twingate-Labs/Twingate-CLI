import json
import pandas as pd
import logging
import GenericTransformers

def GetShowAsCsv(jsonResults):
    columns = ['id', 'firstName','lastName','email','isAdmin','state','groups']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'user',columns)

def GetListAsCsv(jsonResults):
    columns = ['id','firstName','lastName','email','isAdmin','state','groups']
    return GenericTransformers.GetListAsCsv(jsonResults,columns)