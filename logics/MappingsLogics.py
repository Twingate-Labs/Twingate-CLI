import requests
import json
import sys
import os
import urllib.parse
import pandas as pd

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import GroupsTransformers
import StdResponses
import StdAPIUtils

def get_resources_from_group_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor'],"groupID":JsonData['id']}

    Body = """
      query getGroup($cursor: String!,$groupID: ID!)
        {
  group(id:$groupID) {

        resources (after: $cursor) {
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
            pageInfo {
                endCursor
                hasNextPage
            }
        }
  }
}
    """

    return True,api_call_type,Headers,Body,variables
def get_user_groups_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "userEmail":JsonData['email']}

    Body = """
       query listUsers($userEmail: String!)
        {
            users(filter:{email:{eq:$userEmail}}) {
                edges {
                node {
                    id
                    firstName
                    lastName
                    email
                    createdAt
                    updatedAt
                    isAdmin
                    state
                    groups {
                        edges{
                            node{
                                id
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

    return True,api_call_type,Headers,Body,variables

# user query on users with filter -> get user ID and Group IDs
# for each Group ID, get the list of Resource definitions
# return the resource definitions 

# TO DOs
# account for multi page response in Resource list returned
# move formatting code to transformers
def get_user_mappings(outputFormat,sessionname,emailaddr):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_user_groups_resources,{'email':emailaddr})
    
    groupIDs = []
    alledges = j['data']['users']['edges']
    if len(alledges) == 1:
        groups = alledges[0]['node']['groups']['edges']
        if len(groups) == 0:
            print("no group assigned to user.")
        else:
            for grp in groups:
                id = grp['node']['id']
                groupIDs.append(id)
    #else:
    #    print("no corresponding user found.")
        
    allResources = []
    hasMorePages = True
    Cursor = "0"
    for id in groupIDs:

        while hasMorePages:
            a = StdAPIUtils.generic_api_call_handler(sessionname,get_resources_from_group_resources,{'cursor':Cursor,'id':id})
            pInfo = a['data']['group']['resources']['pageInfo']
            hasMorePages = pInfo['hasNextPage']
            if hasMorePages:
                Cursor = pInfo['endCursor']

            allresedges = a['data']['group']['resources']['edges']

            if len(allresedges) != 0:
                for res in allresedges:
                    aResource = res['node']
                    allResources.append(aResource)
            #else:
            #    print("no resource assigned to group.")
            
    df1 = pd.json_normalize(allResources)
    
    if (outputFormat.upper() == "DF"):
        print(df1)
               
    elif (outputFormat.upper() == "CSV"):  
        print(df1.to_csv(index=False))
    else:
        json_formatted_str = json.dumps(allResources, indent=2)
        print(json_formatted_str)
