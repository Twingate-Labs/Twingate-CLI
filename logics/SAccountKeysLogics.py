import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import SAccountKeysTransformers
import StdResponses
import StdAPIUtils

def get_saccount_key_rename_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid'],'name':JsonData['itemname']}
    Body = """
        mutation
            ObjRename($id:ID!,$name:String!){
            serviceAccountKeyUpdate(id: $id, name: $name) {
            ok
            error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_saccount_key_revoke_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid']}
    Body = """
        mutation
            ObjCreate($id:ID!){
                serviceAccountKeyRevoke(id: $id) {
                    ok
                    error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables


def get_saccount_key_delete_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid']}
    Body = """
        mutation
            ObjCreate($id:ID!){
                serviceAccountKeyDelete(id: $id) {
                    ok
                    error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_saccount_key_create_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"name":JsonData['name'],"serviceAccountId":JsonData['serviceAccountId'],'expirationTime':JsonData['expirationTime']}

    Body = """
        mutation
            ObjCreate($name:String!,$serviceAccountId:ID!,$expirationTime:Int!){

            serviceAccountKeyCreate(name: $name, serviceAccountId : $serviceAccountId, expirationTime : $expirationTime ) {
            ok
            error
            token
                entity{
                    id
                    name
                    expiresAt
                    createdAt
                }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_saccount_key_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
        query
            getSAK($itemID: ID!){
                serviceAccountKey(id:$itemID) {
            
                            id
                                    name
                                    createdAt
                                    expiresAt
                                    revokedAt
                                    updatedAt
                                    status
                                    serviceAccount{
                                            id
                                            name
                                    }
        
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def item_create(outputFormat,sessionname,itemname,saccountId,expirationTime):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_saccount_key_create_resources,{'name':itemname,'serviceAccountId':saccountId,'expirationTime':expirationTime},SAccountKeysTransformers.GetCreateAsCsv,"serviceAccountKeyCreate")
    print(r)

def item_delete(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_saccount_key_delete_resources,{'itemid':itemid},GenericTransformers.GetDeleteAsCsv,"serviceAccountKeyDelete")
    print(r)

def item_revoke(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_saccount_key_revoke_resources,{'itemid':itemid},GenericTransformers.GetDeleteAsCsv,"serviceAccountKeyRevoke")
    print(r)

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_saccount_key_show_resources,{'itemid':itemid},SAccountKeysTransformers.GetShowAsCsv,"serviceAccountKey")
    print(r)

def item_rename(outputFormat,sessionname,itemid,itemname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_saccount_key_rename_resources,{'itemid':itemid,'itemname':itemname},GenericTransformers.GetDeleteAsCsv,"serviceAccountKeyUpdate")
    print(r)