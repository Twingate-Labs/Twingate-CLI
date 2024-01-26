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

def get_group_assign_policy_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "groupID":JsonData['itemid'],
        "policyID":JsonData['policyid']
    }

    Body = """
    
mutation assignPolicyToGrp($groupID: ID!, $policyID: ID!){
    groupUpdate(id: $groupID, securityPolicyId: $policyID) {
      ok
      error
      entity{
        id
        name
        isActive
        securityPolicy{
            id
            name
            policyType
        }
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

def get_group_remove_resources_resources(token,JsonData):
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


def get_group_add_resources_resources(token,JsonData):
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

def get_group_delete_resources(token,JsonData):
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
def get_group_create_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    if not JsonData['securityPolicyId']:
        JsonData['securityPolicyId'] = None

    variables = {
        "groupName":JsonData['itemname'],
        "userIDS":JsonData['userids'],
        "resourceIDS":JsonData['resourceids'],
        "securityPolicyId":JsonData['securityPolicyId']
    }

    Body = """
mutation createGroup($groupName: String!, $userIDS: [ID!], $resourceIDS: [ID!], $securityPolicyId: ID){
    groupCreate(name: $groupName, resourceIds: $resourceIDS, userIds: $userIDS, securityPolicyId: $securityPolicyId) {
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

def get_group_remove_users_resources(token,JsonData):
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


def get_group_add_users_resources(token,JsonData):
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


def get_group_list_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    variables = { "cursor":JsonData['cursor']}

    api_call_type = "POST"

    Body = """
    query listGroup($cursor: String!)
            {
  groups(after: $cursor, first:null) {
    pageInfo {
      endCursor
      hasNextPage
    }
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
  }
}

    """

    return True,api_call_type,Headers,Body,variables

def get_group_show_resources(token,JsonData):
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

def assign_policy_to_group(outputFormat,sessionname,itemid,policyid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_assign_policy_resources,{'itemid':itemid,'policyid':policyid})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.AssignPolicyAsCsv)
    print(output)

def add_resources_to_group(outputFormat,sessionname,itemid,resourceids):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_add_resources_resources,{'itemid':itemid,'resourceids':resourceids})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetAddOrRemoveResourcesAsCsv)
    print(output)

def remove_resources_from_group(outputFormat,sessionname,itemid,resourceids):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_remove_resources_resources,{'itemid':itemid,'resourceids':resourceids})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetAddOrRemoveResourcesAsCsv)
    print(output)

def item_delete(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_delete_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetDeleteAsCsv)
    print(output)

def item_create(outputFormat,sessionname,itemname,userids,resourceids,securityPolicyId):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_create_resources,{'itemname':itemname,'userids':userids,'resourceids':resourceids,'securityPolicyId':securityPolicyId})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetCreateAsCsv)
    print(output)

def remove_users_from_group(outputFormat,sessionname,itemid,userids):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_remove_users_resources,{'itemid':itemid,'userids':userids})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetAddOrRemoveUsersAsCsv)
    print(output)

def add_users_to_group(outputFormat,sessionname,itemid,userids):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_add_users_resources,{'itemid':itemid,'userids':userids})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetAddOrRemoveUsersAsCsv)
    print(output)

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_show_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,GroupsTransformers.GetShowAsCsv)
    print(output)

def item_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_group_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'groups')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['groups']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,GroupsTransformers.GetListAsCsv)
    print(output)