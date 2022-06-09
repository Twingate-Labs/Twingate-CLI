import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import StdResponses
import StdAPIUtils

def get_connector_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
        {
          connectors(after: null, first:1000) {
            edges {
              node {
                id
                name
                state
                lastHeartbeatAt
                createdAt
                updatedAt
              }
            }
            pageInfo {
              startCursor
              hasNextPage
            }
          }
        }
    """

    return True,api_call_type,Headers,Body,None

def get_connector_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
         getObj($itemID: ID!){
            connector(id:$itemID) {
                id
                name
                state
                lastHeartbeatAt
                createdAt
                updatedAt
      }
  }
    """

    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_show_resources,{'itemid':itemid},GenericTransformers.GetShowAsCsv,"connector")
    print(r)
def item_list(outputFormat,sessionname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_list_resources,{},GenericTransformers.GetListAsCsv,"connectors")
    print(r)
