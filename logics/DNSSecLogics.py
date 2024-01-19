import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import DNSSecTransformers
import StdResponses
import StdAPIUtils

def get_item_show_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {}

    Body = """
        query CLI_GetDNSFilteringProfile
        {
            dnsFilteringProfile{

                    id
                    allowedDomains
                    deniedDomains
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_set_allow_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "domains":JsonData['domains']
    }

    Body = """
        mutation CLI_SetDNSAllowedDomains($domains:[String!]){
            dnsFilteringAllowedDomainsSet(domains: $domains) {
                ok
                error
            }
        }

    """
    return True,api_call_type,Headers,Body,variables

def get_set_deny_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "domains":JsonData['domains']
    }

    Body = """
        mutation CLI_SetDNSdeniedDomains($domains:[String!]){
            dnsFilteringDeniedDomainsSet(domains: $domains) {
            ok
            error
            }
        }

    """
    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_item_show_resources,{})
    output,r = StdAPIUtils.format_output(j,outputFormat,DNSSecTransformers.GetShowAsCsv)
    print(output)

def set_allow_list(outputFormat,sessionname,domains):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_set_allow_resources,{'domains':domains})
    output,r = StdAPIUtils.format_output(j,outputFormat,DNSSecTransformers.GetUpdateAsCsv)
    print(output)

def set_deny_list(outputFormat,sessionname,domains):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_set_deny_resources,{'domains':domains})
    output,r = StdAPIUtils.format_output(j,outputFormat,DNSSecTransformers.GetBlockAsCsv)
    print(output)
