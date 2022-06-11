import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import RemoteNetworksTransformers
import StdResponses
import StdAPIUtils

def get_network_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
        {
          remoteNetworks(after: null, first:1000) {
            edges {
              node {
                id
        name
        updatedAt
        createdAt
        isActive
        connectors{
            edges{
                node{
                    id
                    name
                }
            }
        }
        resources{
            edges{
                node{
                    id
                    name
                }
            }
        }
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

def get_network_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
            getObj($itemID: ID!){
          remoteNetwork(id:$itemID) {
            id
    name
    updatedAt
    createdAt
    isActive
    connectors{
        edges{
            node{
                id
                name
            }
        }
    }
    resources{
        edges{
            node{
                id
                name
            }
        }
    }
              }
          }
    """

    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_network_show_resources,{'itemid':itemid},RemoteNetworksTransformers.GetShowAsCsv,"remoteNetwork")
    print(r)
    
def item_list(outputFormat,sessionname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_network_list_resources,{},GenericTransformers.GetListAsCsv,"remoteNetworks")
    print(r)
