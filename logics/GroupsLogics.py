import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import GroupsTransformers
import StdResponses
import StdAPIUtils

def get_group_remove_resources_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupID":JsonData['itemid'],
        "resourceIDS":JsonData['resourceids']
    }

    Body = """
        mutation removeResToGroup($groupID: ID!, $resourceIDS: [ID!]){
        groupUpdate(id: $groupID, removedResourceIds: $resourceIDS) {
          ok
          error
          entity{
            id
            name
            isActive
            createdAt
            updatedAt
            type
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


def get_group_add_resources_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupID":JsonData['itemid'],
        "resourceIDS":JsonData['resourceids']
    }

    Body = """
        mutation addResToGroup($groupID: ID!, $resourceIDS: [ID!]){
        groupUpdate(id: $groupID, addedResourceIds: $resourceIDS) {
          ok
          error
          entity{
            id
            name
            isActive
            createdAt
            updatedAt
            type
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

def get_group_delete_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupId":JsonData['itemid']
    }

    Body = """
        mutation deleteGroup($groupId: ID!){
            groupDelete(id: $groupId) {
              ok
              error
            }
        }
    """

    return True,api_call_type,Headers,Body,variables
def get_group_create_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupName":JsonData['itemname'],
        "userIDS":JsonData['userids'],
        "resourceIDS":JsonData['resourceids']
    }

    Body = """
mutation createGroup($groupName: String!, $userIDS: [ID!], $resourceIDS: [ID!]){
    groupCreate(name: $groupName, resourceIds: $resourceIDS, userIds: $userIDS) {
          ok
          error
          entity{
            id
            name
            isActive
            type
            createdAt
            updatedAt
            users {
                edges{
                    node{
                        id
                        email
                        firstName
                        lastName
                    }
                }
            }
            resources {
                edges{
                    node{
                        id
                        name
                        address {
                            type
                            value
                        }
                        isActive
                    }
                }
            }
          }

        }
    }
    """

    return True,api_call_type,Headers,Body,variables

def get_group_remove_users_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupID":JsonData['itemid'],
        "userIDS":JsonData['userids']
    }

    Body = """
        mutation addUsersToGroup($groupID: ID!, $userIDS: [ID!]){
        groupUpdate(id: $groupID, removedUserIds: $userIDS) {
          ok
          error
          entity{
            id
            name
            isActive
            createdAt
            updatedAt
            type
            users {
                edges{
                    node{
                        id
                        email
                        firstName
                        lastName
                    }
                }
            }
          }

        }
    }
    """

    return True,api_call_type,Headers,Body,variables


def get_group_add_users_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupID":JsonData['itemid'],
        "userIDS":JsonData['userids']
    }

    Body = """
        mutation addUsersToGroup($groupID: ID!, $userIDS: [ID!]){
        groupUpdate(id: $groupID, addedUserIds: $userIDS) {
          ok
          error
          entity{
            id
            name
            isActive
            createdAt
            updatedAt
            type
            users {
                edges{
                    node{
                        id
                        email
                        firstName
                        lastName
                    }
                }
            }
          }

        }
    }
    """

    return True,api_call_type,Headers,Body,variables


def get_group_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
            {
  groups(after: null, first:1000) {
    edges {
      node {
        id
        name
        createdAt
        updatedAt
        isActive
        type
        users {
            edges{
                node{
                    id
                    email
                    firstName
                    lastName
                }
            }
        }
        resources {
            edges{
                node{
                    id
                    name
                    address {
                        type
                        value
                    }
                    isActive
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

def get_group_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
         getObj($itemID: ID!){
            group(id:$itemID) {
                        id
                        name
                        createdAt
                        updatedAt
                        isActive
                        type
                        users {
                            edges{
                                node{
                                    id
                                    email
                                    firstName
                                    lastName
                                }
                            }
                        }
                        resources {
                            edges{
                                node{
                                    id
                                    name
                                    address {
                                        type
                                        value
                                    }
                                    isActive
                                }
                            }
                        }
      }
  }
    """

    return True,api_call_type,Headers,Body,variables

def add_resources_to_group(outputFormat,sessionname,itemid,resourceids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_add_resources_resources,{'itemid':itemid,'resourceids':resourceids},GroupsTransformers.GetAddOrRemoveResourcesAsCsv,'groupUpdate')
    print(r)

def remove_resources_from_group(outputFormat,sessionname,itemid,resourceids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_remove_resources_resources,{'itemid':itemid,'resourceids':resourceids},GroupsTransformers.GetAddOrRemoveResourcesAsCsv,'groupUpdate')
    print(r)

def item_delete(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_delete_resources,{'itemid':itemid},GenericTransformers.GetDeleteAsCsv,'groupDelete')
    print(r)

def item_create(outputFormat,sessionname,itemname,userids,resourceids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_create_resources,{'itemname':itemname,'userids':userids,'resourceids':resourceids},GroupsTransformers.GetCreateAsCsv,'groupCreate')
    print(r)

def remove_users_from_group(outputFormat,sessionname,itemid,userids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_remove_users_resources,{'itemid':itemid,'userids':userids},GroupsTransformers.GetAddOrRemoveUsersAsCsv,'groupUpdate')
    print(r)

def add_users_to_group(outputFormat,sessionname,itemid,userids):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_add_users_resources,{'itemid':itemid,'userids':userids},GroupsTransformers.GetAddOrRemoveUsersAsCsv,'groupUpdate')
    print(r)

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_show_resources,{'itemid':itemid},GroupsTransformers.GetShowAsCsv,"group")
    print(r)
def item_list(outputFormat,sessionname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_group_list_resources,{},GroupsTransformers.GetListAsCsv,'groups')
    print(r)
