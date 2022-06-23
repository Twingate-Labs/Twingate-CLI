import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import UsersTransformers
import GenericTransformers
import StdResponses
import StdAPIUtils

def get_user_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = { "cursor":JsonData['cursor']}

    Body = """
    query listGroup($cursor: String!)
            {
          users(after: $cursor, first:null) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                id
               	avatarUrl
                state
                email
                state
                isAdmin
                lastName
                firstName
                createdAt
                updatedAt
                groups{
                  edges{
                    node{
                      id
                    }
                  }
                }
              }
            }

          }
        }
    """

    return True,api_call_type,Headers,Body,variables

def get_user_show_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"
    variables = {"itemID":JsonData['itemid']}
    Body = """
         query
            getObj($itemID: ID!){
          user(id:$itemID) {
                id
               	avatarUrl
                state
                email
                state
                isAdmin
                lastName
                firstName
                createdAt
                updatedAt
                groups{
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

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_user_show_resources,{'itemid':itemid},UsersTransformers.GetShowAsCsv)
    print(r)

def item_list(outputFormat,sessionname):
  ListOfResponses = []
  hasMorePages = True
  Cursor = "0"
  while hasMorePages:
    j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_user_list_resources,{'cursor':Cursor},UsersTransformers.GetListAsCsv)
    hasMorePages,Cursor = GenericTransformers.CheckIfMorePages(j,'users')
    #print("DEBUG: Has More pages:"+sthasMorePages)
    ListOfResponses.append(j['data']['users']['edges'])
  
  output,r = StdAPIUtils.format_output(ListOfResponses,outputFormat,UsersTransformers.GetListAsCsv)
  print(output)