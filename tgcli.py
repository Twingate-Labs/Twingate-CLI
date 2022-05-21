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
import RemoteNetworksLogics
import ServiceAccountsLogics
import ResourcesLogics
import UsersLogics
import GroupsLogics
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
    DevicesLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# Device commands
device_parser = subparsers.add_parser('device')
device_subparsers = device_parser.add_subparsers()

# device list
device_list_parser = device_subparsers.add_parser('list')
device_list_parser.set_defaults(func=device_list)

# device <show>

def device_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no device ID passed')

    DevicesLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# device show
device_show_parser = device_subparsers.add_parser('show')
device_show_parser.set_defaults(func=device_show)
device_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# device <updateTrust>

def device_update(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID and not args.ITEMLIST:
        parser.error('no device ID or device List passed')
    if args.ITEMID and args.ITEMLIST:
        parser.error('either item ID or item List can be passed, not both')

    isMatchToTrue = re.match('True', str(args.TRUST), re.IGNORECASE)
    isMatchToFalse = re.match('False', str(args.TRUST), re.IGNORECASE)
    if isMatchToTrue:
        args.TRUST = True
    if isMatchToFalse:
        args.TRUST = False
    if not isMatchToTrue and not isMatchToFalse:
        parser.error('-trust value must be True or False')

    if args.ITEMLIST:
        AllItems = args.ITEMLIST.split(",")

    else:
        AllItems = [args.ITEMID]

    for item in AllItems:
        DevicesLogics.item_update(args.OUTPUTFORMAT,args.SESSIONNAME,item,args.TRUST)

device_update_parser = device_subparsers.add_parser('updateTrust')
device_update_parser.set_defaults(func=device_update)

device_update_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
device_update_parser.add_argument('-l','--itemlist',type=str,default="", help='item list ex: "id1,id2,id3"', dest="ITEMLIST")
device_update_parser.add_argument('-t','--trust',type=str,default=True, help='True or False',dest="TRUST")


#####
# Connector Parser
# connector <list>
#####

def connector_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ConnectorsLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# connector commands
connector_parser = subparsers.add_parser('connector')
connector_subparsers = connector_parser.add_subparsers()

# connector list
connector_list_parser = connector_subparsers.add_parser('list')
connector_list_parser.set_defaults(func=connector_list)

# connector <show>

def connector_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    ConnectorsLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# connector show
connector_show_parser = connector_subparsers.add_parser('show')
connector_show_parser.set_defaults(func=connector_show)
connector_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

#####
# User Parser
# user <list>
#####

def user_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    UsersLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# user commands
user_parser = subparsers.add_parser('user')
user_subparsers = user_parser.add_subparsers()

# user list
user_list_parser = user_subparsers.add_parser('list')
user_list_parser.set_defaults(func=user_list)

# user <show>

def user_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    UsersLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# user show
user_show_parser = user_subparsers.add_parser('show')
user_show_parser.set_defaults(func=user_show)
user_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


#####
# Group Parser
# group <list>
#####

def group_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    GroupsLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# group commands
group_parser = subparsers.add_parser('group')
group_subparsers = group_parser.add_subparsers()

# group list
group_list_parser = group_subparsers.add_parser('list')
group_list_parser.set_defaults(func=group_list)

# group <show>

def group_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    GroupsLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# group show
group_show_parser = group_subparsers.add_parser('show')
group_show_parser.set_defaults(func=group_show)
group_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

#####
# Resource Parser
# resource <list>
#####

def resource_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ResourcesLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# resource commands
resource_parser = subparsers.add_parser('resource')
resource_subparsers = resource_parser.add_subparsers()

# resource list
resource_list_parser = resource_subparsers.add_parser('list')
resource_list_parser.set_defaults(func=resource_list)

# resource <show>

def resource_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no resource ID passed')

    ResourcesLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# resource show
resource_show_parser = resource_subparsers.add_parser('show')
resource_show_parser.set_defaults(func=resource_show)
resource_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# resource <create>

def resource_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ADDRESS:
        parser.error('no address passed')
    if not args.NAME:
        parser.error('no name passed')
    if not args.NETWORKID:
        parser.error('no network ID passed')
    if args.GROUPIDS != []:
        AllIDs = args.GROUPIDS.split(",")
        args.GROUPIDS = AllIDs

    ResourcesLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ADDRESS,args.NAME,args.NETWORKID,args.GROUPIDS)

resource_create_parser = resource_subparsers.add_parser('create')
resource_create_parser.set_defaults(func=resource_create)

resource_create_parser.add_argument('-a','--address',type=str,default="", help='resource address', dest="ADDRESS")
resource_create_parser.add_argument('-n','--name',type=str,default="", help='resource name', dest="NAME")
resource_create_parser.add_argument('-r','--networkID',type=str,default="", help='remote network ID', dest="NETWORKID")
resource_create_parser.add_argument('-g','--groupIDs',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")

# resource <delete>

def resource_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    ResourcesLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# resource show
resource_delete_parser = resource_subparsers.add_parser('delete')
resource_delete_parser.set_defaults(func=resource_delete)
resource_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


#####
# Remote Network Parser
# network <list>
#####

def network_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    RemoteNetworksLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# network commands
network_parser = subparsers.add_parser('network')
network_subparsers = network_parser.add_subparsers()

# network list
network_list_parser = network_subparsers.add_parser('list')
network_list_parser.set_defaults(func=network_list)

# network <show>

def network_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    RemoteNetworksLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# network show
network_show_parser = network_subparsers.add_parser('show')
network_show_parser.set_defaults(func=network_show)
network_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

#####
# Service Account Parser
# account <list>
#####

def account_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ServiceAccountsLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# account commands
account_parser = subparsers.add_parser('account')
account_subparsers = account_parser.add_subparsers()

# account list
account_list_parser = account_subparsers.add_parser('list')
account_list_parser.set_defaults(func=account_list)

# account <show>

def account_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    ServiceAccountsLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# account show
account_show_parser = account_subparsers.add_parser('show')
account_show_parser.set_defaults(func=account_show)
account_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


if __name__ == '__main__':
    args = parser.parse_args()
    args.func(args)
