##############################################################
#
# Author: Bren Sapience
# Date: Mar 2022
# Scope: Wrapper CLI around Twingate Admin APIs
#
#
##############################################################
#!/usr/bin/env python3
# install pandas
import argparse
import sys
import logging
sys.path.insert(1, './logics')
sys.path.insert(1, './libs')
import AuthLogics
import DevicesLogics
import ConnectorsLogics
import ResourcesLogics
import UsersLogics
import DataUtils
import re

VERSION="0.0.1"

logging.basicConfig(level=logging.ERROR)

#####
# General Parser
#####

parser = argparse.ArgumentParser()
parser.add_argument('-v','--version', action='version', version=VERSION)
parser.add_argument('-s','--session',type=str,default="", help='Session Name',dest="SESSIONNAME")
parser.add_argument('-f','--format',type=str,default="JSON", help='Output Format <JSON,CSV,DF>',dest="OUTPUTFORMAT")
subparsers = parser.add_subparsers()

#####
# AUTH Parser
# Authentication commands
# auth <login,logout,list>
#####

def login(args):
    if not args.APIKEY:
        parser.error('no api key passed')
    if not args.URL:
        parser.error('no url passed')
    if not args.SESSIONNAME:
        args.SESSIONNAME = DataUtils.RandomSessionNameGenerator()
    AuthLogics.login(args.APIKEY,args.URL,args.SESSIONNAME)

def logout(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    AuthLogics.logout(args.SESSIONNAME)

def listsessions(args):
    AuthLogics.listSessions()

auth_parser = subparsers.add_parser('auth')
auth_subparsers = auth_parser.add_subparsers()

# auth login
login_parser = auth_subparsers.add_parser('login')
login_parser.add_argument('-a','--api_key',type=str,default="", help='API Key', dest="APIKEY")
login_parser.add_argument('-s','--session',type=str,default="", help='Session Name (Optional)',dest="SESSIONNAME")
login_parser.add_argument('-r', '--url',type=str,default="", help='Twingate API URL',dest="URL")
#login_parser.add_argument('-v', '--version',type=str,default=DEFAULT_CR_VERSION, help='CR Version',dest="CRVERSION")
#login_parser.add_argument('-s', '--session',type=str,default="", help='Session Name',dest="SESSIONNAME")
login_parser.set_defaults(func=login)

# auth logout
login_parser = auth_subparsers.add_parser('logout')
login_parser.add_argument('-s', '--session',type=str,default="", help='Session Name',dest="SESSIONNAME")
login_parser.set_defaults(func=logout)

# auth list
sesslist_parser = auth_subparsers.add_parser('list')
sesslist_parser.set_defaults(func=listsessions)


#####
# Device Parser
# device <list>
#####

def device_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    DevicesLogics.device_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# Device commands
device_parser = subparsers.add_parser('device')
device_subparsers = device_parser.add_subparsers()

# device list
device_list_parser = device_subparsers.add_parser('list')
device_list_parser.set_defaults(func=device_list)

# device <updateTrust>

def device_update(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.DEVICEID and not args.DEVICELIST:
        parser.error('no device ID or device List passed')
    if args.DEVICEID and args.DEVICELIST:
        parser.error('either device ID or device List can be passed, not both')

    isMatchToTrue = re.match('True', str(args.TRUST), re.IGNORECASE)
    isMatchToFalse = re.match('False', str(args.TRUST), re.IGNORECASE)
    if isMatchToTrue:
        args.TRUST = True
    if isMatchToFalse:
        args.TRUST = False
    if not isMatchToTrue and not isMatchToFalse:
        parser.error('-trust value must be True or False')

    if args.DEVICELIST:
        AllDevices = args.DEVICELIST.split(",")

    else:
        AllDevices = [args.DEVICEID]

    for device in AllDevices:
        DevicesLogics.device_update(args.OUTPUTFORMAT,args.SESSIONNAME,device,args.TRUST)

device_update_parser = device_subparsers.add_parser('updateTrust')
device_update_parser.set_defaults(func=device_update)

device_update_parser.add_argument('-i','--deviceid',type=str,default="", help='device id', dest="DEVICEID")
device_update_parser.add_argument('-l','--devicelist',type=str,default="", help='device list ex: "id1,id2,id3"', dest="DEVICELIST")
device_update_parser.add_argument('-t','--trust',type=str,default=True, help='True or False',dest="TRUST")


#####
# Connector Parser
# connector <list>
#####

def connector_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ConnectorsLogics.connector_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# Device commands
connector_parser = subparsers.add_parser('connector')
connector_subparsers = connector_parser.add_subparsers()

# device list
connector_list_parser = connector_subparsers.add_parser('list')
connector_list_parser.set_defaults(func=connector_list)


#####
# User Parser
# user <list>
#####

def user_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    UsersLogics.user_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# user commands
user_parser = subparsers.add_parser('user')
user_subparsers = user_parser.add_subparsers()

# user list
user_list_parser = user_subparsers.add_parser('list')
user_list_parser.set_defaults(func=user_list)


#####
# Resource Parser
# resource <list>
#####

def resource_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ResourcesLogics.resource_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# resource commands
resource_parser = subparsers.add_parser('resource')
resource_subparsers = resource_parser.add_subparsers()

# resource list
resource_list_parser = resource_subparsers.add_parser('list')
resource_list_parser.set_defaults(func=resource_list)

if __name__ == '__main__':
    args = parser.parse_args()
    args.func(args)
