import requests
import json
import sys
import os
import urllib.parse
import array

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import ResourcesTransformers
import StdResponses
import StdAPIUtils


def get_resource_update_autolock(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"autolock":JsonData['autolock']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$autolock:Int!){
    resourceUpdate(id: $itemid, usageBasedAutolockDurationDays: $autolock) {
      ok
      error
        entity {   
                id
                name
                alias
                usageBasedAutolockDurationDays
                address{
                    type
                    value
                }
                remoteNetwork{
                    id
                    name
                }
            }
        }
    
    }

    """
    return True,api_call_type,Headers,Body,variables

def get_resource_update_alias(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"alias":JsonData['alias']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$alias:String!){
    resourceUpdate(id: $itemid, alias: $alias) {
      ok
      error
        entity {   
                id
                name
                alias
                usageBasedAutolockDurationDays
                address{
                    type
                    value
                }
                remoteNetwork{
                    id
                    name
                }
            }
        }
    
    }

    """
    return True,api_call_type,Headers,Body,variables

def get_resource_update_address(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"address":JsonData['address']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$address:String!){
    resourceUpdate(id: $itemid, address: $address) {
      ok
      error
        entity {
                   
                id
                name
                alias
                usageBasedAutolockDurationDays
                address{
                    type
                    value
                }
                remoteNetwork{
                    id
                    name
                }
            }
        }
    
    }

    """

    return True,api_call_type,Headers,Body,variables  

def get_resource_update_policy(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"securityPolicyId":JsonData['securityPolicyId']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$securityPolicyId: ID!){
    resourceUpdate(id: $itemid, securityPolicyId: $securityPolicyId) {
      ok
      error
        entity {
                   
                id
                name
                alias
                usageBasedAutolockDurationDays
                securityPolicy {
                id
              }
            }
        }
    
    }

    """

    return True,api_call_type,Headers,Body,variables  

def get_resource_toggle_visibility(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"visibility":JsonData['visibility']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$visibility:Boolean!){
    resourceUpdate(id: $itemid, isVisible: $visibility) {
      ok
      error
       entity {
            id
            name
            isVisible
            isBrowserShortcutEnabled
            }
    }
}

    """

    return True,api_call_type,Headers,Body,variables  

def get_resource_assign_network_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"itemid":JsonData['itemid'] ,"networkid":JsonData['networkid']}
    #print(variables)
    Body = """
    mutation
    ObjUpdate($itemid: ID!,$networkid:ID!){
        resourceUpdate(id: $itemid, remoteNetworkId: $networkid) {
        ok
        error
        entity {
                id
                name
                alias
                address{
                    type
                    value
                }
                remoteNetwork{
                    id
                    name
                }
            }
        }
    }

    """

    return True,api_call_type,Headers,Body,variables   

def get_resource_create_resources(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"address":JsonData['address'] ,"alias":JsonData['alias'],"name":JsonData['name'],"remoteNetworkId":JsonData['remoteNetworkId'],"groupIds":JsonData['groupIds'],"protocols":JsonData['protocols'],"securityPolicyId":JsonData['securityPolicyId'],"isVisible":JsonData['isVisible']}
    #print(variables)
    Body = """
        mutation
ObjCreate($address: String!,$alias: String,$name:String!,$remoteNetworkId:ID!,$groupIds:[ID!],$protocols:ProtocolsInput!,$securityPolicyId:ID!,$isVisible:Boolean!){
            resourceCreate(protocols: $protocols, address: $address, alias: $alias, groupIds: $groupIds, name: $name, remoteNetworkId: $remoteNetworkId, securityPolicyId: $securityPolicyId, isVisible: $isVisible) {
              ok
              error
            entity{
              id
              name
              isVisible
              securityPolicy {
                id
              }
            }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_resource_delete_resources(token,JsonData):
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

def get_resource_list_resources(token,JsonData):
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
                        isActive
                        name
                        alias
                        createdAt
                        updatedAt
                        isVisible
                        isBrowserShortcutEnabled
                        access{
                            edges{
                                node{
                                    ... on Group {
                                        id
                                        name
                                    }
                                    ... on ServiceAccount {
                                        id
                                        name
                                    }
                                }
                            
                                securityPolicy {
                                    id
                                    name
                                }
                            }
                        }
                        securityPolicy {
                            id
                            name
                        }
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
                    }
                }
            }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_resource_show_resources(token,JsonData):
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
        isVisible
        isBrowserShortcutEnabled
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

def get_resource_access_remove(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"groupid":JsonData['groupid'],"itemid":JsonData['itemid']}
    #print(variables)

    Body = """

    mutation
    ObjUpdate($itemid: ID!,$groupid:[ID!]!){
    resourceAccessRemove(principalIds: $groupid, resourceId: $itemid) {
      ok
      error
        entity {   
                id
            }
        }
    }
    """
    return True,api_call_type,Headers,Body,variables

def get_resource_access_set(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    AccessArray = []
    api_call_type = "POST"
    if JsonData['serviceid']:
        sids =  JsonData['serviceid'].split(',')
        for sid in sids:
            tmpDict = dict()
            tmpDict['principalId'] = sid
            tmpDict['securityPolicyId'] = None
            if JsonData['autolockdays']:
                tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
            if JsonData['expiresat']:
                tmpDict['expiresAt'] = JsonData['expiresat']
            AccessArray.append(tmpDict)
    if JsonData['groupid']:
        gids = JsonData['groupid'].split(',')
        pols = JsonData['policyid'].split(',')
        if len(pols) != 1:
            i = 0
            while (i < len(gids)):
                print("gidsing " + str(i) + " " + gids[i])
                tmpDict = dict()
                tmpDict['principalId'] = gids[i]
                tmpDict['securityPolicyId'] = pols[i]
                if JsonData['autolockdays']:
                    tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
                if JsonData['expiresat']:
                    tmpDict['expiresAt'] = JsonData['expiresat']
                AccessArray.append(tmpDict)
                i += 1
        else: 
            for gid in gids:
                tmpDict = dict()
                tmpDict['principalId'] = gid
                tmpDict['securityPolicyId'] = pols[0]
                if JsonData['autolockdays']:
                    tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
                if JsonData['expiresat']:
                    tmpDict['expiresAt'] = JsonData['expiresat']
                AccessArray.append(tmpDict)
   
    variables = {"accessids":AccessArray,"itemid":JsonData['itemid']}
    Body = """

    mutation 
        ObjUpdate($accessids: [AccessInput!]!, $itemid: ID!) {
        resourceAccessSet(access: $accessids, resourceId: $itemid) {
            ok
            error
            entity {
                id
                createdAt
                updatedAt
                name
            }
        }
    }

    """
    return True,api_call_type,Headers,Body,variables


def get_resource_access_add(token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    AccessArray = []
    api_call_type = "POST"
    if JsonData['serviceid']:
        sids =  JsonData['serviceid'].split(',')
        for sid in sids:
            tmpDict = dict()
            tmpDict['principalId'] = sid
            tmpDict['securityPolicyId'] = None
            if JsonData['autolockdays']:
                tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
            if JsonData['expiresat']:
                tmpDict['expiresAt'] = JsonData['expiresat']
            AccessArray.append(tmpDict)
    if JsonData['groupid']:
        gids = JsonData['groupid'].split(',')
        pols = JsonData['policyid'].split(',')
        if len(pols) != 1:
            i = 0
            while (i < len(gids)):
                print("gidsing " + str(i) + " " + gids[i])
                tmpDict = dict()
                tmpDict['principalId'] = gids[i]
                tmpDict['securityPolicyId'] = pols[i]
                if JsonData['autolockdays']:
                    tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
                if JsonData['expiresat']:
                    tmpDict['expiresAt'] = JsonData['expiresat']
                AccessArray.append(tmpDict)
                i += 1
        else: 
            for gid in gids:
                tmpDict = dict()
                tmpDict['principalId'] = gid
                tmpDict['securityPolicyId'] = pols[0]
                if JsonData['autolockdays']:
                    tmpDict['usageBasedAutolockDurationDays'] = JsonData['autolockdays']
                if JsonData['expiresat']:
                    tmpDict['expiresAt'] = JsonData['expiresat']
                AccessArray.append(tmpDict)
   
    variables = {"accessids":AccessArray,"itemid":JsonData['itemid']}
    Body = """

    mutation 
        ObjUpdate($accessids: [AccessInput!]!, $itemid: ID!) {
        resourceAccessAdd(access: $accessids, resourceId: $itemid) {
            ok
            error
            entity {
                id
                createdAt
                updatedAt
                name
            }
        }
    }

    """
    return True,api_call_type,Headers,Body,variables



def item_delete(outputFormat,sessionname,itemid):
    JsonData = {"itemid":itemid}
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_delete_resources,JsonData)
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetDeleteAsCsv)
    print(output)

def item_create(outputFormat,sessionname,address,alias,name,remoteNetworkId,groupIds,IcmpAllow,TcpPolicy,TcpRange,UdpPolicy,UdpRange,PolicyId,isVisible):
    JsonData = {"address":address,"alias":alias,"name":name,"remoteNetworkId":remoteNetworkId,"securityPolicyId":PolicyId,"groupIds":groupIds,"isVisible":isVisible, "protocols":{"allowIcmp":IcmpAllow,"tcp":{"policy":TcpPolicy,"ports":TcpRange},"udp":{"policy":UdpPolicy,"ports":UdpRange}}}
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_create_resources,JsonData)
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetCreateAsCsv)
    print(output)

def item_list(outputFormat,sessionname):
    #r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_resource_list_resources,{},ResourcesTransformers.GetListAsCsv)
    #print(r)
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_list_resources,{'cursor':Cursor})
        hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'resources')
        #print("DEBUG: Has More pages:"+sthasMorePages)
        ListOfResponses.append(j['data']['resources']['edges'])
    output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,ResourcesTransformers.GetListAsCsv)
    print(output)

def item_show(outputFormat,sessionname,itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_show_resources,{'itemid':itemid})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetShowAsCsv)
    print(output)

def assign_network_to_resource(outputFormat,sessionname,itemid,networkid):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_assign_network_resources,{'itemid':itemid,'networkid':networkid})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)

def update_visibility(outputFormat,sessionname,itemid,isVisible):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_toggle_visibility,{'itemid':itemid,'visibility':isVisible})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetVisibilityUpdateAsCsv)
    print(output)

def update_address(outputFormat,sessionname,itemid,address):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_update_address,{'itemid':itemid,'address':address})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)
    #get_resource_update_address

def update_alias(outputFormat,sessionname,itemid,alias):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_update_alias,{'itemid':itemid,'alias':alias})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)
    #get_resource_update_address

def update_policy(outputFormat,sessionname,itemid,securityPolicyId):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_update_policy,{'itemid':itemid,'securityPolicyId':securityPolicyId})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)
    #get_resource_update_address

def access_remove(outputFormat,sessionname,itemid,groupid):
    groupid = groupid.split(",")
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_access_remove,{'itemid':itemid,'groupid':groupid})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)

def access_set(outputFormat,sessionname,itemid,groupid,serviceid,policyid,autolockdays,expiresat):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_access_set,{'itemid':itemid,'groupid':groupid,'serviceid':serviceid,'policyid':policyid,'autolockdays':autolockdays,'expiresat':expiresat})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)

def access_add(outputFormat,sessionname,itemid,groupid,serviceid,policyid,autolockdays,expiresat):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_access_add,{'itemid':itemid,'groupid':groupid,'serviceid':serviceid,'policyid':policyid,'autolockdays':autolockdays,'expiresat':expiresat})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)

def update_autolock(outputFormat,sessionname,itemid,autolock):
    j = StdAPIUtils.generic_api_call_handler(sessionname,get_resource_update_autolock,{'itemid':itemid,'autolock':autolock})
    output,r = StdAPIUtils.format_output(j,outputFormat,ResourcesTransformers.GetUpdateAsCsv)
    print(output)
    #get_resource_update_address