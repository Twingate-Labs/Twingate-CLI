import requests
import json
import sys
import os

sys.path.insert(1, './libs')
import DataUtils
import StdResponses

# don't think the below function is used anymore
#def Process_Auth_Login_Response(res):
#    if(res.status_code==200):
#        try:
#            result = json.loads(res.text)
#            if 'error' in result:
#                DSMAPIRetCode = result['error']['code']
#                #print("Code: "+str(DSMAPIRetCode))
#                return True,DSMAPIRetCode

#            if 'token' in result:
#                TOKEN = result['token']
#                #print(TOKEN)
#                return False,TOKEN
#        except:
#            print("Unknown Error.")
#            return True,""
