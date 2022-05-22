import requests
import json
import sys
import os
import urllib.parse

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import DataUtils
import GenericTransformers
import StdResponses
import StdAPIUtils

def get_user_list_resources(sessionname,token,JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)

    api_call_type = "POST"

    Body = """
            {
          users(after: null, first:100) {
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
              }
          }
    """

    return True,api_call_type,Headers,Body,variables

def item_show(outputFormat,sessionname,itemid):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_user_show_resources,{'itemid':itemid},GenericTransformers.GetShowAsCsv,"user")
    print(r)

def item_list(outputFormat,sessionname):
    r,j = StdAPIUtils.generic_api_call_handler(outputFormat,sessionname,get_user_list_resources,{},GenericTransformers.GetListAsCsv,'users')
    print(r)
