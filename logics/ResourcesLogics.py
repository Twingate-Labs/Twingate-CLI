import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import ResourcesTransformers
import StdResponses
import StdAPIUtils

def get_resource_create_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"address":JsonData['address'] ,"name":JsonData['name'],"remoteNetworkId":JsonData['remoteNetworkId'],"groupIds":JsonData['groupIds']}
    #print(variables)
    Body = """
        mutation
            ObjCreate($address: String!,$name:String!,$remoteNetworkId:ID!,$groupIds:[ID!]){
            resourceCreate(address: $address, groupIds: $groupIds, name: $name, remoteNetworkId: $remoteNetworkId) {
              ok
              error
            entity{
              id
              name
            }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_resource_delete_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"id":JsonData['itemid']}
    #print(variables)
    Body = """
        mutation
            ObjDelete($id: ID!){
            resourceDelete(id: $id) {
              ok
              error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_resource_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
                    {
          resources(after: null, first:1000) {
            edges {
              node {
                id
                remoteNetwork{
                    name
                }
               	address{
                    type
                    value
                }
                protocols {
                allowIcmp
                tcp {
                    policy
                    ports {
                        start
                        end
                    }
                }
                udp{
                    policy
                    ports {
                        start
                        end
                    }
                }
                }
                isActive
                name
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

def get_resource_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
    getResource($itemID: ID!){
        resource(id:$itemID) {
        id
        name
        createdAt
        updatedAt
        isActive
        remoteNetwork{
            name
        }
        address {
                type
                value
                }
        protocols {
                allowIcmp
                tcp {
                    policy
                    ports {
                        start
                        end
                    }
                }
                udp{
                    policy
                    ports {
                        start
                        end
                    }
                }
        }
      }
  }

    """

    return True,api_call_type,Headers,Body,variables

def item_delete(outputFormat,sessionname,itemid):
    JsonData = {"itemid":itemid}
    StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_delete_resources,JsonData,GenericTransformers.GetDeleteAsCsv,'resourceDelete')

def item_create(outputFormat,sessionname,address,name,remoteNetworkId,groupIds):
    JsonData = {"address":address,"name":name,"remoteNetworkId":remoteNetworkId,"groupIds":groupIds}
    StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_create_resources,JsonData,GenericTransformers.GetCreateAsCsv,'resourceCreate')

def item_list(outputFormat,sessionname):
    StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_list_resources,{},GenericTransformers.GetListAsCsv,'resources')

def item_show(outputFormat,sessionname,itemid):
    StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_show_resources,{'itemid':itemid},ResourcesTransformers.GetShowAsCsv,"resources")
