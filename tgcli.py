##############################################################
#
# Author: Bren Sapience - brendan@twingate.com
# Date: Mar 2022
# Scope: Wrapper CLI around Twingate Admin APIs
#
##############################################################

#!/usr/bin/env python3
# don't forget to pip install pandas!
import argparse
import sys
import logging
import re
sys.path.insert(1, './logics')
sys.path.insert(1, './validators')
sys.path.insert(1, './libs')
import AuthLogics
import DevicesLogics
import ConnectorsLogics
import RemoteNetworksLogics
import ServiceAccountsLogics
import ResourcesLogics
import UsersLogics
import GroupsLogics
import ProtocolValidators
import DataUtils


VERSION="1.0.0"

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
    if not args.TENANT:
        parser.error('no Network Tenant passed')
    if not args.SESSIONNAME:
        args.SESSIONNAME = DataUtils.RandomSessionNameGenerator()
    AuthLogics.login(args.APIKEY,args.TENANT,args.SESSIONNAME)

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
login_parser.add_argument('-a','--apikey',type=str,default="", help='API Key', dest="APIKEY")
login_parser.add_argument('-s','--session',type=str,default="", help='Session Name (Optional)',dest="SESSIONNAME")
login_parser.add_argument('-t', '--tenant',type=str,default="", help='Twingate Network Tenant',dest="TENANT")
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
    if args.IDPATH and args.IDSONLY:
        parser.error('you cannot pass -f and -i together.')
    DevicesLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME,args.IDPATH,args.IDSONLY)

# Device commands
device_parser = subparsers.add_parser('device')
device_subparsers = device_parser.add_subparsers()

# device list
device_list_parser = device_subparsers.add_parser('list')
device_list_parser.set_defaults(func=device_list)
device_list_parser.add_argument('-l','--fileofids',type=str,default="", help='Compare IDs to existing list from file', dest="IDPATH")
device_list_parser.add_argument('-i','--idsonly',type=bool,default=False, help='Print Only Ids', dest="IDSONLY")

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

# group <addResources>

def group_add_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.RESIDS != []:
        AllIDs = args.RESIDS.split(",")
        args.RESIDS = AllIDs
    GroupsLogics.add_users_to_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# group addUsers
group_addresources_parser = group_subparsers.add_parser('addResources')
group_addresources_parser.set_defaults(func=group_add_resources)
group_addresources_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_addresources_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESIDS")

# group <removeResources>

def group_remove_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.RESIDS != []:
        AllIDs = args.RESIDS.split(",")
        args.RESIDS = AllIDs
    GroupsLogics.remove_resources_from_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# group removeResources
group_removeresources_parser = group_subparsers.add_parser('removeResources')
group_removeresources_parser.set_defaults(func=group_remove_resources)
group_removeresources_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_removeresources_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESIDS")

# group <addResources>

def group_add_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.RESIDS != []:
        AllIDs = args.RESIDS.split(",")
        args.RESIDS = AllIDs
    GroupsLogics.add_resources_to_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# group addResources
group_addusers_parser = group_subparsers.add_parser('addResources')
group_addusers_parser.set_defaults(func=group_add_resources)
group_addusers_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_addusers_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESIDS")

# group <removeUsers>

def group_remove_users(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.USERIDS != []:
        AllIDs = args.USERIDS.split(",")
        args.USERIDS = AllIDs
    GroupsLogics.remove_users_from_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.USERIDS)

# group removeUsers
group_addusers_parser = group_subparsers.add_parser('removeUsers')
group_addusers_parser.set_defaults(func=group_remove_users)
group_addusers_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_addusers_parser.add_argument('-u','--userids',type=str,default=[], help='list of User IDs, ex: "id1","id2"', dest="USERIDS")

# group <create>

def group_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMNAME:
        parser.error('no item name passed')
    if args.USERIDS != []:
        AllIDs = args.USERIDS.split(",")
        args.USERIDS = AllIDs
    if args.RESOURCEIDS != []:
        AllIDs = args.RESOURCEIDS.split(",")
        args.RESOURCEIDS = AllIDs
    GroupsLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMNAME,args.USERIDS,args.RESOURCEIDS)

# group removeUsers
group_create_parser = group_subparsers.add_parser('create')
group_create_parser.set_defaults(func=group_create)
group_create_parser.add_argument('-g','--groupname',type=str,default="", help='group name', dest="ITEMNAME")
group_create_parser.add_argument('-u','--userids',type=str,default=[], help='list of User IDs, ex: "id1","id2"', dest="USERIDS")
group_create_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESOURCEIDS")

# group <delete>

def group_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item name passed')
    GroupsLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# group removeUsers
group_delete_parser = group_subparsers.add_parser('delete')
group_delete_parser.set_defaults(func=group_delete)
group_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

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

    isSuccess,ret = ProtocolValidators.ValidateRange(args.TCPRANGE)
    if not isSuccess:
        parser.error(str(args.TCPRANGE)+" - "+ret)
    else:
        args.TCPRANGE=ret

    isSuccess,ret = ProtocolValidators.ValidatePolicy(args.TCPPOLICY)
    if not isSuccess:
        parser.error(str(args.TCPPOLICY)+" - "+ret)

    isSuccess,ret = ProtocolValidators.ValidateRange(args.UDPRANGE)
    if not isSuccess:
        parser.error(str(args.UDPRANGE)+" - "+ret)
    else:
        args.UDPRANGE=ret

    isSuccess,ret = ProtocolValidators.ValidatePolicy(args.TCPPOLICY,)
    if not isSuccess:
        parser.error(str(args.UDPPOLICY)+" - "+ret)

    isSuccess,ret = ProtocolValidators.ValidateRangeWithPolicy(str(args.TCPRANGE),args.TCPPOLICY)
    if not isSuccess:
        parser.error(ret)

    isSuccess,ret = ProtocolValidators.ValidateRangeWithPolicy(str(args.UDPRANGE),args.UDPPOLICY)
    if not isSuccess:
        parser.error(ret)

    #exit(1)
    ResourcesLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ADDRESS,args.NAME,args.NETWORKID,args.GROUPIDS,not args.DISALLOWICMP,args.TCPPOLICY,args.TCPRANGE,args.UDPPOLICY,args.UDPRANGE)

resource_create_parser = resource_subparsers.add_parser('create')
resource_create_parser.set_defaults(func=resource_create)

resource_create_parser.add_argument('-a','--address',type=str,default="", help='resource address', dest="ADDRESS")
resource_create_parser.add_argument('-n','--name',type=str,default="", help='resource name', dest="NAME")
resource_create_parser.add_argument('-r','--networkid',type=str,default="", help='remote network ID', dest="NETWORKID")
resource_create_parser.add_argument('-g','--groupids',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")
resource_create_parser.add_argument('-i','--icmp',type=bool,default=False, help='(Optional) Disallow ICMP Protocol', dest="DISALLOWICMP")
resource_create_parser.add_argument('-t','--tcppolicy',type=str,default="ALLOW_ALL", help='(Optional) <ALLOW_ALL,DENY_ALL>, Default: ALLOW_ALL', dest="TCPPOLICY")
resource_create_parser.add_argument('-c','--tcprange',type=str,default="[]", help='(Optional) <[[a,b],[c,d],..]>, Default: [], ex:[[22-50],[443,443],[654-987]]', dest="TCPRANGE")
resource_create_parser.add_argument('-u','--udppolicy',type=str,default="ALLOW_ALL", help='(Optional) <ALLOW_ALL,DENY_ALL>, Default: ALLOW_ALL', dest="UDPPOLICY")
resource_create_parser.add_argument('-d','--udprange',type=str,default="[]", help='(Optional) <[[a,b],[c,d],..]>, Default: [], ex:[[22-50],[443,443],[654-987]]', dest="UDPRANGE")

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
    #try:
    args.func(args)
    #except:
    #    print("general error, please check commands & parameters. Hint: Use -h")
