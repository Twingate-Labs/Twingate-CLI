import requests
import json
import sys
import logging
import os
import urllib.parse
sys.path.insert(1, './libs')
sys.path.insert(1, './responses')
sys.path.insert(1, './transformers')
import DataUtils
import StdResponses

def get_api_call_headers(token):
    DefaultHeaders = {
        'X-API-KEY': token,
        'User-agent': 'TwingatePythonCLI/1.0.0'
    }

    return DefaultHeaders

# Generic API Handler with embedded processing of Output
def generic_api_call_handler(sessionname,get_res_func,res_data):
        url,tenant = DataUtils.GetUrl(sessionname)
        TOKEN = DataUtils.GetAuthToken(tenant,sessionname)

        isSupported,CallType,Headers,Body,variables = get_res_func(TOKEN,res_data)

        FULLURL = url
        
        logging.debug("method:"+str(CallType))
        logging.debug("URL:"+str(url))
        logging.debug("Data:"+str(Body))
        logging.debug("headers:"+str(Headers))
        logging.debug("variables:" + str(variables))

        if variables:
            response = requests.request(method=CallType, url=FULLURL, json={'query': Body, 'variables':variables}, headers=Headers)
        else:
            response = requests.request(method=CallType, url=FULLURL, json={'query': Body}, headers=Headers)
        
        logging.debug("Response:" + str(response.text))
        logging.debug("status code:"+str(response.status_code))
        isAPICallOK = StdResponses.processAPIResponse(response)

        if(not isAPICallOK):
            exit(99)
        else:
            logging.debug("Converting Response to JSON Object.")
            json_object = json.loads(response.text)
            return json_object

def format_output(json_object,outputFormat,df_transform_func):

    # check if there is a next page
            # if so get cursor and apply again

    if (outputFormat.upper() == "DF"):
        logging.debug("Converting JSON Object to DF.")
        aDF = df_transform_func(json_object)
        return aDF,json_object
               
    elif (outputFormat.upper() == "CSV"):
                
        logging.debug("Converting JSON Object to CSV.")
        aDF = df_transform_func(json_object)
        #print(aDF.to_csv(index=False))
        return aDF.to_csv(index=False),json_object
    else:
        logging.debug("Keeping JSON Object to JSON.")
        json_formatted_str = json.dumps(json_object, indent=2)
        #print(json_formatted_str)
        return json_formatted_str,json_object