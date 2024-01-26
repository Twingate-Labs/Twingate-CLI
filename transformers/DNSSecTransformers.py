import json
import pandas as pd
import logging
import GenericTransformers

def GetUpdateAllowAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'dnsFilteringAllowedDomainsSet',columns)

def GetUpdateDenyAsCsv(jsonResults):
    columns = ['ok','error']
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'dnsFilteringDeniedDomainsSet',columns)

def GetShowAsCsv(jsonResults):
    columns = ['id', 'allowedDomains','deniedDomains']

    return GenericTransformers.GetShowAsCsvNoNesting(jsonResults,'dnsFilteringProfile',columns)