import requests
import json
import sys
import os
import urllib.parse
import pandas as pd
import logging

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import GroupsTransformers
import StdResponses
import StdAPIUtils
import TGUtils

def get_resources_from_user_rn_mappings(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
query getUsers ($cursor: String!)
{
  users(after: $cursor) {
    edges {
      node {
        id
        firstName
        lastName
        email
        groups {
            edges {
                node {
                    name
                    resources {
                        edges {
                            node {
                                id
                                name
                                remoteNetwork {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }

      }
    }
    pageInfo {
      endCursor
      hasNextPage
    }
  }
}
    """

    return True,api_call_type,Headers,Body,variables

def get_resources_from_group_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor'],"groupID":JsonData['id']}

    Body = """
      query getGroup($cursor: String!,$groupID: ID!)
        {
  group(id:$groupID) {
        id
        name
        resources (after: $cursor) {
            edges{
                node{
                    id
                    name
                    address {
                        type
                        value
                    }
                    remoteNetwork {
                    id
                    name

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


def get_user_rn_mapping(outputFormat,sessionname):
    hasMorePages = True
    Cursor = "0"

    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resources_from_user_rn_mappings,{'cursor':Cursor})
    logging.debug("output of groups assigned to user: "+str(j))
    allUsers = []
    while hasMorePages:
        a = StdAPIUtils.generic_api_call_handler(sessionname,get_resources_from_user_rn_mappings,{'cursor':Cursor})
        pInfo = a['data']['users']['pageInfo']
        logging.debug("pagination info: "+str(pInfo))
        hasMorePages = pInfo['hasNextPage']
        if hasMorePages:
            Cursor = pInfo['endCursor']
        #userEdges = a['data']['users']['edges']
        allUsers.append(a['data']['users']['edges'])
    
    # [[{'node': {'id': 'VXNlcjoxOTU5NA==', 'firstName': 'Alex', 'lastName': 'Marshall', 'email': 'alexm@twindemo.com', 'groups': {'edges': [{'node': {'name': 'Everyone', 'resources': {'edges': [{'node': {'remoteNetwork': {'name': 'AWS Twindemo'}}}
    alluserinfo = []
    for node in allUsers:
        for user in node:
            allRNS = []
            allResources = []
            username = user['node']['email']
            groups = user['node']['groups']['edges']
            for group in groups:
                resources = group['node']['resources']['edges']
                
                
                for res in resources:
                    resname = res['node']['name']
                    resid = res['node']['id']
                    rnname = res['node']['remoteNetwork']['name']
                    rnid = res['node']['remoteNetwork']['id']

                    if rnname not in allRNS:
                        allRNS.append(rnname)

                    if resname not in allResources:
                        allResources.append(resname)

            #print(username)
            #print(len(allRNS))
            #print(len(allResources))

            entry = {
                "user.email":username,
                "networks.count":len(allRNS),
                "resources.count":len(allResources),
                "networks": allRNS,
                "resources": allResources
            }

            alluserinfo.append(entry)
            #print(entry)
    
    df1 = pd.json_normalize(alluserinfo)
    #print(df1)

    if (outputFormat.upper() == "DF"):
        logging.debug("Converting JSON Object to DF.")
        print(df1)
               
    elif (outputFormat.upper() == "CSV"):
                
        logging.debug("Converting JSON Object to CSV.")
        #print(aDF.to_csv(index=False))
        print(df1.to_csv(index=False))
    else:
        logging.debug("Keeping JSON Object to JSON.")
        json_formatted_str = json.dumps(alluserinfo, indent=2)
        print(json_formatted_str)


# user query on users with filter -> get user ID and Group IDs
# for each Group ID, get the list of Resource definitions
# return the resource definitions 
def get_user_mappings(outputFormat,sessionname,emailaddr,fqdn):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_user_groups_resources,{'email':emailaddr})
    logging.debug("output of groups assigned to user: "+str(j))
    groupIDs = []
    alledges = j['data']['users']['edges']
    
    if len(alledges) == 1:
        groups = alledges[0]['node']['groups']['edges']
        if len(groups) == 0:
            print("no group assigned to user.")
            
        else:
            logging.debug("groups assigned to user: "+str(groups))
            for grp in groups:
                id = grp['node']['id']
                groupIDs.append(id)
    #else:
    #    print("no corresponding user found.")
        
    allResources = []
    
    for id in groupIDs:
        hasMorePages = True
        Cursor = "0"
        logging.debug("retrieving resources for ID: "+str(id))
        while hasMorePages:
            a = StdAPIUtils.generic_api_call_handler(sessionname,get_resources_from_group_resources,{'cursor':Cursor,'id':id})
            pInfo = a['data']['group']['resources']['pageInfo']
            logging.debug("pagination info: "+str(pInfo))
            hasMorePages = pInfo['hasNextPage']
            if hasMorePages:
                Cursor = pInfo['endCursor']

            allresedges = a['data']['group']['resources']['edges']
            grpid = a['data']['group']['id']
            grpname = a['data']['group']['name']
            logging.debug("resources retrieved: "+str(allresedges))
            if len(allresedges) != 0:
                for res in allresedges:
                    aResource = res['node']
                    aResource['group.id']=grpid
                    aResource['group.name']=grpname
                    allResources.append(aResource)
            #else:
            #    print("no resource assigned to group.")
            
    df1 = pd.json_normalize(allResources)
    
    if fqdn != "":
        df1['matchFqdn'] = df1['address.value'].apply(TGUtils.does_addr_match_res_definition,args=(fqdn,))

        df_fqdn_matches = df1.loc[df1["matchFqdn"] == True]

        df_duplicates = df_fqdn_matches[df_fqdn_matches.duplicated(['id'])]

        ordered_list_of_resources = TGUtils.resource_definition_matcher2(df_fqdn_matches)
        
        ordered_list_of_resources2 = TGUtils.resource_definition_matcher(df_fqdn_matches['address.value'].tolist())
        nb_ambiguities,ambiguitylist = TGUtils.detect_res_definition_ambiguity(ordered_list_of_resources2)
        #print(ambiguitylist)

        if (outputFormat.upper() == "CSV"): 
            print("\nAll Resources available for User:")
            if df1.empty:
                print("None")
            else:
                print(df1.to_csv(index=False))

            print("\nResources matching FQDN:")
            if df_fqdn_matches.empty:
                print("None")
            else:
                print(df_fqdn_matches.to_csv(index=False))

            print("\nOrdered list of Resources:")
            if ordered_list_of_resources.empty:
                print("None")
            else:
                print(ordered_list_of_resources.to_csv(index=False))

            print("\nDuplicate Resources (served by more than 1 Group):")
            if df_duplicates.empty:
                print("None")
            else:       
                print(df_duplicates.to_csv(index=False)) 

        # for DF or JSON (JSON cannot be supported here)
        else:
            print("\nAll Resources available for User:")
            if df1.empty:
                print("None")
            else:
                print(df1)

            print("\nResources matching FQDN:")
            if df_fqdn_matches.empty:
                print("None")
            else:
                print(df_fqdn_matches)

            print("\nOrdered list of Resources:")
            if ordered_list_of_resources.empty:
                print("None")
            else:
                print(ordered_list_of_resources)

            print("\nDuplicate Resources (served by more than 1 Group):")
            if df_duplicates.empty:
                print("None")
            else:       
                print(df_duplicates)
        
        if nb_ambiguities > 0:
            print("\nlist of pairs of conflicting resource definitions found: "+str(ambiguitylist))
        
        else:
            print("\nNo conflicting resource definitions found.")
        
    else:
        if (outputFormat.upper() == "CSV"): 
            if df1.empty:
                print("None")
            else:
                print(df1.to_csv(index=False))
        else:
            if df1.empty:
                print("None")
            else:
                print(df1)


