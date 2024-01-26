import requests
import json
import sys
import os
import logging

def ProcessBool(myBool):
    if(str(type(myBool)) == "<class 'str'>"):
        if(myBool in ['True','true','t','yes']):
            return True
        if(myBool in ['False','false','f','no']):
            return False
    else:
        return myBool

def isAnomalousHtmlResponse(text):
    if("<html" in text and "</html>" in text):
        return True
    else:
        return False

def processAPIResponse(response):
    if(response.status_code >= 300):
        if(response.status_code == 500):
            logging.debug("API Error: {} - Hint: {} - Message: {}".format(response.status_code, "Try logging back in.",response.text))
            print("API Error: {} - Hint: {} - Message: {}".format(response.status_code, "Try logging back in.",response.text))
            #print("API Error Code: "+str(response.status_code))
            return False
        else:
            logging.debug("API Error: {} - Message: {}".format(response.status_code,response.text))
            print("API Error: {} - Message: {}".format(response.status_code,response.text))
            #print("API Error Code: "+str(response.status_code))
            return False
    else:
        RespContent = str(response.text)
        if(RespContent.startswith("<!doctype html>")):
            logging.debug("API Error: {} - Message: {}".format(response.status_code,"Response received is in HTML Format"))
            print("API Error: {} - Message: {}".format(response.status_code,"Response received is in HTML Format"))
            return False
        else:
            return True

def ProcessStdResponse(res,CsvOutput):
    CsvOutput = ProcessBool(CsvOutput)
    if isAnomalousHtmlResponse(res.text):
        print("Error: You need to log back in.")
        exit(1)
    if(res.status_code >= 400):

        print("Error Code: "+str(res.status_code))
        try:
            result = json.loads(res.text)
            if result['message']:
                print("Error Message: "+result['details'])
                return True,None
        except:
            return True,None

        return True,None

    else:
        try:
            return False,CsvOutput
        except:
            print("Unknown Error.")
            return True,None
