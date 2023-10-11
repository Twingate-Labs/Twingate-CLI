import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import ConnectorsTransformers
import GenericTransformers
import StdResponses
import StdAPIUtils


def get_connector_create_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'connName':JsonData['connName'], 'remoteNetworkID':JsonData['remoteNetworkID'],'statNotifications':JsonData['statNotifications']}

    Body = """
        mutation connectorCreate($connName: String!, $remoteNetworkID: ID!, $statNotifications: Boolean){
            connectorCreate(name: $connName,remoteNetworkId: $remoteNetworkID, hasStatusNotificationsEnabled: $statNotifications) {
                ok
                error
                entity{
                    id
                    name
                    state
                    lastHeartbeatAt
                    hasStatusNotificationsEnabled
                    remoteNetwork{
                        id
                        name
                    }
                }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_connector_generate_tokens_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid']}
    Body = """
        mutation
            GetConnTokens($id:ID!){
            connectorGenerateTokens(connectorId: $id) {
            ok
            error
            connectorTokens {
      accessToken
      refreshToken
    }
            }
        }
    """
    return True,api_call_type,Headers,Body,variables

def get_connector_update_email_notification_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid'],'hasStatusNotificationsEnabled':JsonData['hasStatusNotificationsEnabled']}
    Body = """
        mutation
            ObjUpd($id:ID!,$hasStatusNotificationsEnabled:Boolean!){
            connectorUpdate(id: $id, hasStatusNotificationsEnabled: $hasStatusNotificationsEnabled) {
            ok
            error
            entity{
              id
              name
              hasStatusNotificationsEnabled
            }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_connector_rename_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid'],'name':JsonData['itemname']}
    Body = """
        mutation
            ObjRename($id:ID!,$name:String!){
            connectorUpdate(id: $id, name: $name) {
            ok
            error
            entity{
              id
              name
              hasStatusNotificationsEnabled
            }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_connector_list_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
        query listObj($cursor: String!)
        {
          connectors(after: $cursor, first:null) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                id
                name
                state
                hostname
                version
                publicIP
                privateIPs
                lastHeartbeatAt
                createdAt
                updatedAt
                hasStatusNotificationsEnabled
              }
            }
          }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_connector_show_resources(token,JsonData):
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
            hostname
            version
            publicIP
            privateIPs
            lastHeartbeatAt
            hasStatusNotificationsEnabled
            remoteNetwork{
                id
                name
            }
          }
      }
    """

    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_connector_show_resources,{'itemid':itemid})
    #print(r)
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetShowAsCsv)
    print(output)

def item_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_connector_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'connectors')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['connectors']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,ConnectorsTransformers.GetListAsCsv)
    print(output)

def item_rename(outputFormat,sessionname,itemid,itemname):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_connector_rename_resources,{'itemid':itemid,'itemname':itemname})
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetUpdateAsCsv)
    print(output)

def item_change_status_notification(outputFormat,sessionname,itemid,hasStatusNotificationsEnabled):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_connector_update_email_notification_resources,{'itemid':itemid,'hasStatusNotificationsEnabled':hasStatusNotificationsEnabled})
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetUpdateAsCsv)
    print(output)

def item_get_tokens(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_connector_generate_tokens_resources,{'itemid':itemid},ConnectorsTransformers.GetGenTokensAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetGenTokensAsCsv)
    print(output)

#     variables = {'connName':JsonData['connName'], 'remoteNetworkID':JsonData['remoteNetworkID'],'statNotifications':JsonData['statNotifications']}
def item_create(outputFormat,sessionname,connName,remoteNetworkID,statNotifications):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_connector_create_resources,{'connName':connName,'remoteNetworkID':remoteNetworkID,'statNotifications':statNotifications})
    output,r = StdAPIUtils.format_output(j,outputFormat,ConnectorsTransformers.GetCreateAsCsv)
    print(output)