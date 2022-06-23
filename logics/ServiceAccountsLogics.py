import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import ServiceAccountsTransformers
import StdResponses
import StdAPIUtils


def get_service_account_remove_resources_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "id":JsonData['itemid'],
        "resourceIDS":JsonData['resourceids']
    }

    Body = """
        mutation removeResToSAccount($id: ID!, $resourceIDS: [ID!]){
        serviceAccountUpdate(id: $id, removedResourceIds: $resourceIDS) {
          ok
          error
          entity{
            id
            name
            createdAt
            updatedAt
            resources {
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
    """

    return True,api_call_type,Headers,Body,variables


def get_service_account_add_resources_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "id":JsonData['itemid'],
        "resourceIDS":JsonData['resourceids']
    }

    Body = """
        mutation addResToSAccount($id: ID!, $resourceIDS: [ID!]){
        serviceAccountUpdate(id: $id, addedResourceIds: $resourceIDS) {
          ok
          error
          entity{
            id
            name
            createdAt
            updatedAt
            resources {
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
    """

    return True,api_call_type,Headers,Body,variables

def get_service_account_delete_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {'id':JsonData['itemid']}
    Body = """
        mutation
            ObjCreate($id:ID!){
                serviceAccountDelete(id: $id) {
                    ok
                    error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_service_account_create_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"name":JsonData['name'],"resourceIds":JsonData['resourceIds']}
    Body = """
        mutation
            ObjCreate($name:String!,$resourceIds:[ID!]){

                serviceAccountCreate(name: $name, resourceIds : $resourceIds) {
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

def get_service_account_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
       {
        serviceAccounts(after: null, first:null) {
            edges {
            node {
                id
                name
                createdAt
                updatedAt
                resources{
                    edges{
                        node{
                            id
                            name
                        }
                    }
                }
                keys {
                    edges{
                        node{
                            id
                            name
                            createdAt
                            expiresAt
                            revokedAt
                            updatedAt
                            status
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

def get_service_account_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
            getObj($itemID: ID!){
          serviceAccount(id:$itemID) {
                id
                name
                createdAt
                updatedAt
                resources {
                    edges{
                        node{
   id
                        name
                        }
                     
                    }
                }
                keys {
                    edges{
                        node{
                            id
                            name
                            createdAt
                            expiresAt
                            revokedAt
                            updatedAt
                            status
                        }
                    }

                }
              }
          }
    """

    return True,api_call_type,Headers,Body,variables

def item_create(outputFormat,sessionname,itemname,resourceIds):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_create_resources,{'name':itemname,'resourceIds':resourceIds},ServiceAccountsTransformers.GetCreateAsCsv)
    print(r)

def item_delete(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_delete_resources,{'itemid':itemid},ServiceAccountsTransformers.GetDeleteAsCsv)
    print(r)

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_show_resources,{'itemid':itemid},ServiceAccountsTransformers.GetShowAsCsv)
    print(r)

def item_list(outputFormat,sessionname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_list_resources,{},ServiceAccountsTransformers.GetListAsCsv)
    print(r)

def add_resources_to_saccount(outputFormat,sessionname,itemid,resourceids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_add_resources_resources,{'itemid':itemid,'resourceids':resourceids},ServiceAccountsTransformers.GetAddOrRemoveResourcesAsCsv)
    print(r)

def remove_resources_from_saccount(outputFormat,sessionname,itemid,resourceids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_service_account_remove_resources_resources,{'itemid':itemid,'resourceids':resourceids},ServiceAccountsTransformers.GetAddOrRemoveResourcesAsCsv)
    print(r)
