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
    variables = {"address":JsonData['address'] ,"name":JsonData['name'],"remoteNetworkId":JsonData['remoteNetworkId'],"groupIds":JsonData['groupIds'],"protocols":JsonData['protocols']}
    #print(variables)
    Body = """
        mutation
            ObjCreate($address: String!,$name:String!,$remoteNetworkId:ID!,$groupIds:[ID!],$protocols:ProtocolsInput!){
            resourceCreate(protocols: $protocols, address: $address, groupIds: $groupIds, name: $name, remoteNetworkId: $remoteNetworkId) {
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
    variables = { "cursor":JsonData['cursor']}
    Body = """
    
        query listGroup($cursor: String!)
                    {
          resources(after: $cursor, first:null) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                id
                remoteNetwork{
                    name
                    id
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

          }
        }
    """

    return True,api_call_type,Headers,Body,variables

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
            id
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
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_delete_resources,JsonData,ResourcesTransformers.GetDeleteAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetDeleteAsCsv)
    print(output)

def item_create(outputFormat,sessionname,address,name,remoteNetworkId,groupIds,IcmpAllow,TcpPolicy,TcpRange,UdpPolicy,UdpRange):
    JsonData = {"address":address,"name":name,"remoteNetworkId":remoteNetworkId,"groupIds":groupIds,"protocols":{"allowIcmp":IcmpAllow,"tcp":{"policy":TcpPolicy,"ports":TcpRange},"udp":{"policy":UdpPolicy,"ports":UdpRange}}}
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_create_resources,JsonData,ResourcesTransformers.GetCreateAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetCreateAsCsv)
    print(output)

def item_list(outputFormat,sessionname):
    #r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_list_resources,{},ResourcesTransformers.GetListAsCsv)
    #print(r)
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_list_resources,{'cursor':Cursor},ResourcesTransformers.GetListAsCsv)
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'resources')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['resources']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,ResourcesTransformers.GetListAsCsv)
    print(output)


def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_show_resources,{'itemid':itemid},ResourcesTransformers.GetShowAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetShowAsCsv)
    print(output)

