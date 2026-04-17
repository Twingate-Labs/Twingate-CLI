import json
import pandas as pd
import logging
import GenericTransformers


def GetListAsCsv(jsonResults):
    columns = ['id', 'name', 'description', 'type', 'action', 'status', 'createdAt', 'updatedAt']
    return GenericTransformers.GetListAsCsv(jsonResults, columns)


def GetShowAsCsv(jsonResults):
    columns = ['id', 'name', 'description', 'type', 'action', 'status', 'createdAt', 'updatedAt']
    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults, 'devicePostureCheck', columns)


def GetCreateAsCsv(jsonResults):
    columns = ['ok', 'error', 'id', 'name', 'description', 'type', 'action', 'status']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckCreate', columns)


def GetUpdateAsCsv(jsonResults):
    columns = ['ok', 'error', 'id', 'name', 'description', 'type', 'action', 'status']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckUpdate', columns)


def GetDeleteAsCsv(jsonResults):
    columns = ['ok', 'error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults, 'devicePostureCheckDelete', columns)
