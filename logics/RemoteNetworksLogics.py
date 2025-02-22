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

def get_network_delete_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"id":JsonData['itemid']}
    Body = """
        mutation
    ObjDelete($id:ID!){

    remoteNetworkDelete(id: $id) {
      ok
      error
    }
}

    """

    return True,api_call_type,Headers,Body,variables

def get_network_create_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"name":JsonData['name'],"location":JsonData['location'],"isactive":JsonData['isactive']}
    Body = """
         mutation
            ObjCreate($name:String!,$location:RemoteNetworkLocation!,$isactive:Boolean!){

            remoteNetworkCreate(name: $name, location: $location, isActive:$isactive) {
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

def get_network_list_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
    query listGroup($cursor: String!)
        {
          remoteNetworks(after: $cursor, first:null) {
            pageInfo {
              endCursor
              hasNextPage
            }
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

          }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_network_show_resources(token,JsonData):
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


def get_network_updateState_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"rnID":JsonData['itemid'],"state":JsonData['state']}
    Body = """
    mutation
    PM_UpdateRemoteNetwork($rnID:ID!,$state:Boolean!){

    remoteNetworkUpdate(id: $rnID,isActive:$state ) {
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

def get_network_updateName_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"rnID":JsonData['itemid'],"name":JsonData['name']}
    Body = """
    mutation
    PM_UpdateRemoteNetwork($rnID:ID!,$name:String!){
    remoteNetworkUpdate(id: $rnID,name:$name ) {
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

def get_network_updateLocation_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"rnID":JsonData['itemid'],"location":JsonData['location']}
    Body = """
    mutation
    PM_UpdateRemoteNetwork($rnID:ID!,$location:RemoteNetworkLocation!){

    remoteNetworkUpdate(id: $rnID,location:$location ) {
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

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_show_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetShowAsCsv)
    print(output)
    
def item_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'remoteNetworks')
        ListOfResponses.append(j['data']['remoteNetworks']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,RemoteNetworksTransformers.GetListAsCsv)
    print(output)

def item_create(outputFormat,sessionname,name,location,isactive):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_create_resources,{'name':name,'location':location,'isactive':isactive})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetCreateAsCsv)
    print(output)

def item_delete(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_delete_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetDeleteAsCsv)
    print(output)

def update_state(outputFormat,sessionname,itemid,state):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_updateState_resources,{'itemid':itemid,'state':state})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetUpdateAsCsv)
    print(output)

def update_name(outputFormat,sessionname,itemid,name):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_updateName_resources,{'itemid':itemid,'name':name})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetUpdateAsCsv)
    print(output)

def update_location(outputFormat,sessionname,itemid,location):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_network_updateLocation_resources,{'itemid':itemid,'location':location})
    output,r = StdAPIUtils.format_output(j,outputFormat,RemoteNetworksTransformers.GetUpdateAsCsv)
    print(output)

def GetUpdateAsCsv(jsonResults):
    columns = ['ok','error','id', 'name']
    #GenericTransformers.GetUpdateAsCsvNoNesting()
    return GenericTransformers.GetUpdateAsCsvNoNesting(jsonResults,'remoteNetworkUpdate',columns)