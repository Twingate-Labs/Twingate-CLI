import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import SecurityPoliciesTransformers
import StdResponses
import StdAPIUtils

def get_policy_set_groups_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "policyID":JsonData['itemid'],
        "groupIDS":JsonData['groupids']
    }

    Body = """
      mutation setGroupsToPolicy($policyID: ID!, $groupIDS: [ID!]){
    securityPolicyUpdate(id: $policyID, groupIds: $groupIDS) {
      ok
      error
      entity{
        id
        name
        updatedAt
        createdAt
        policyType
        groups {
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

def get_policy_remove_groups_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "policyID":JsonData['itemid'],
        "groupIDS":JsonData['groupids']
    }

    Body = """
      mutation addGroupsToPolicy($policyID: ID!, $groupIDS: [ID!]){
    securityPolicyUpdate(id: $policyID, removedGroupIds: $groupIDS) {
      ok
      error
      entity{
        id
        name
        updatedAt
        createdAt
        policyType
        groups {
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

def get_policy_add_groups_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {
        "policyID":JsonData['itemid'],
        "groupIDS":JsonData['groupids']
    }

    Body = """
      mutation addGroupsToPolicy($policyID: ID!, $groupIDS: [ID!]){
    securityPolicyUpdate(id: $policyID, addedGroupIds: $groupIDS) {
      ok
      error
      entity{
        id
        name
        updatedAt
        createdAt
        policyType
        groups {
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

def get_secpol_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
    query listObj($cursor: String!)
    {
          securityPolicies(after: $cursor, first:null) {
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
                policyType
        groups {
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
        }"""

    return True,api_call_type,Headers,Body,variables

def get_secpol_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
            getObj($itemID: ID!){
          securityPolicy(id:$itemID) {
               id
        name
        updatedAt
        createdAt
        policyType
        groups {
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

def item_list(outputFormat,sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_secpol_list_resources,{'cursor':Cursor},SecurityPoliciesTransformers.GetListAsCsv)
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'securityPolicies')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['securityPolicies']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,SecurityPoliciesTransformers.GetListAsCsv)
    print(output)

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_secpol_show_resources,{'itemid':itemid},SecurityPoliciesTransformers.GetShowAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,SecurityPoliciesTransformers.GetShowAsCsv)
    print(output)

def remove_groups_from_policy(outputFormat,sessionname,itemid,groupids):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_policy_remove_groups_resources,{'itemid':itemid,'groupids':groupids},SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    print(output)

def add_groups_to_policy(outputFormat,sessionname,itemid,groupids):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_policy_add_groups_resources,{'itemid':itemid,'groupids':groupids},SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    print(output)

def set_groups_for_policy(outputFormat,sessionname,itemid,groupids):
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_policy_set_groups_resources,{'itemid':itemid,'groupids':groupids},SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    output,r = StdAPIUtils.format_output(j,outputFormat,SecurityPoliciesTransformers.GetAddOrRemoveGroupsAsCsv)
    print(output)