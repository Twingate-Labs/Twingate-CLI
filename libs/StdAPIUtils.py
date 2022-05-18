import requests
import json
import sys
import os
import urllib.parse
sys.path.insert(1, './libs')
sys.path.insert(1, './responses')
sys.path.insert(1, './transformers')
import DataUtils
import StdResponses

def get_api_call_headers(token):
    DefaultHeaders = {
        'X-API-KEY': token
    }

    return DefaultHeaders

# Generic API Handler with embedded processing of Output
def generic_api_call_handler_old(outputFormat,sessionname,get_res_func,res_data,df_transform_func,objectname):
        url = DataUtils.GetUrl(sessionname)
        TOKEN = DataUtils.GetAuthToken(sessionname)

        isSupported,CallType,Headers,Body = get_res_func(sessionname,TOKEN,res_data)

        FULLURL = url
        #print("method:"+str(CallType)+" - URL:"+str(url)+ " - data:"+str(Body)+ " - headers:"+str(Headers))

        response = requests.request(method=CallType, url=FULLURL, json={'query': Body}, headers=Headers)
        isAPICallOK = StdResponses.processAPIResponse(response)
        if(not isAPICallOK):
            exit(99)
        else:
            json_object = json.loads(response.text)
            if (outputFormat == "DF"):
                #print(json_object)
                aDF = df_transform_func(json_object,objectname)
                print(aDF)
            elif (outputFormat == "CSV"):
                #print(json_object)
                aDF = df_transform_func(json_object,objectname)
                print(aDF.to_csv(index=False))
            else:
                #print(json_object)
                json_formatted_str = json.dumps(json_object, indent=2)
                print(json_formatted_str)

# Generic API Handler with embedded processing of Output
def generic_api_call_handler(outputFormat,sessionname,get_res_func,res_data,df_transform_func,objectname):
        url = DataUtils.GetUrl(sessionname)
        TOKEN = DataUtils.GetAuthToken(sessionname)

        isSupported,CallType,Headers,Body,variables = get_res_func(sessionname,TOKEN,res_data)

        FULLURL = url
        #print("method:"+str(CallType)+" - URL:"+str(url)+ " - data:"+str(Body)+ " - headers:"+str(Headers)+ " - variables:" + str(variables))
        if variables:
            response = requests.request(method=CallType, url=FULLURL, json={'query': Body, 'variables':variables}, headers=Headers)
        else:
            response = requests.request(method=CallType, url=FULLURL, json={'query': Body}, headers=Headers)

        isAPICallOK = StdResponses.processAPIResponse(response)
        #print("debug:"+response.text)
        if(not isAPICallOK):
            exit(99)
        else:
            json_object = json.loads(response.text)
            if (outputFormat == "DF"):
                #print(json_object)
                aDF = df_transform_func(json_object,objectname)
                print(aDF)
            elif (outputFormat == "CSV"):
                #print(json_object)
                aDF = df_transform_func(json_object,objectname)
                print(aDF.to_csv(index=False))
            else:
                #print(json_object)
                json_formatted_str = json.dumps(json_object, indent=2)
                print(json_formatted_str)
