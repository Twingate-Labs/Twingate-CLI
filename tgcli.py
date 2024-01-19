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
import textwrap
import array
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
import RNValidators
import ServiceAccountKeyValidators
import UserValidators
import GenericValidators
import DataUtils
import SAccountKeysLogics
import SecPoliciesLogics
import MappingsLogics
import DNSSecLogics

VERSION="1.0.0"



#####
# General Parser
#####

parser = argparse.ArgumentParser()
parser.add_argument('-v','--version', action='version', version=VERSION)
parser.add_argument('-l','--log',default="ERROR", help='DEBUG,INFO,WARNING,ERROR', dest="DEBUGLEVEL")
parser.add_argument('-s','--session',type=str,default="", help='Session Name',dest="SESSIONNAME")
parser.add_argument('-f','--format',type=str,default="JSON", help='Output Format <JSON,CSV,DF>',dest="OUTPUTFORMAT")
subparsers = parser.add_subparsers()

#logging.basicConfig(level=logging.ERROR)


# Unabashedly taken from https://stackoverflow.com/a/64102901 so that we can have newlines in our descriptive text.

from argparse import ArgumentParser, HelpFormatter

class RawFormatter(HelpFormatter):
    def _fill_text(self, text, width, indent):
        return "\n".join([textwrap.fill(line, width) for line in textwrap.indent(textwrap.dedent(text), indent).splitlines()])

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


# device <block | unblock | archive>

def device_block_unblock_archive(Type,args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no device ID passed')

    if Type == "BLOCK":
        DevicesLogics.item_block(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

    if Type == "UNBLOCK":
        DevicesLogics.item_unblock(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

    if Type == "ARCHIVE":
        DevicesLogics.item_archive(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)


def device_block(args):
    device_block_unblock_archive("BLOCK",args)

device_block_parser = device_subparsers.add_parser('block')
device_block_parser.set_defaults(func=device_block)
device_block_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


def device_unblock(args):
    device_block_unblock_archive("UNBLOCK",args)

device_unblock_parser = device_subparsers.add_parser('unblock')
device_unblock_parser.set_defaults(func=device_unblock)
device_unblock_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

def device_archive(args):
    device_block_unblock_archive("ARCHIVE",args)

device_archive_parser = device_subparsers.add_parser('archive')
device_archive_parser.set_defaults(func=device_archive)
device_archive_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


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

# connector <rename>

def connector_rename(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ITEMNAME:
        parser.error('no item name passed')

    ConnectorsLogics.item_rename(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.ITEMNAME)

# connector rename
connector_rename_parser = connector_subparsers.add_parser('rename')
connector_rename_parser.set_defaults(func=connector_rename)
connector_rename_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
connector_rename_parser.add_argument('-n','--itemname',type=str,default="", help='new item name', dest="ITEMNAME")


# connector <updateNotifications>

def connector_updnotification(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.NOTIFICATION:
        parser.error('no flag for notifications passed')
    isOK,Value = GenericValidators.checkStringAsBool(args.NOTIFICATION)
    if not isOK:
        parser.error('wrong value passed for parameter updateNotifications (true or false)')
    else:
        args.NOTIFICATION=Value

    ConnectorsLogics.item_change_status_notification(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.NOTIFICATION)

# connector updateNotifications
connector_updnotification_parser = connector_subparsers.add_parser('updateNotifications')
connector_updnotification_parser.set_defaults(func=connector_updnotification)
connector_updnotification_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
connector_updnotification_parser.add_argument('-s','--sendnotifications',type=str,default="true", help='true or false', dest="NOTIFICATION")

# connector generate tokens

def connector_generate_tokens(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    ConnectorsLogics.item_get_tokens(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# connector generate_tokens
connector_gentokens_parser = connector_subparsers.add_parser('generateTokens')
connector_gentokens_parser.set_defaults(func=connector_generate_tokens)
connector_gentokens_parser.add_argument('-i','--itemid',type=str,default="", help='connector id', dest="ITEMID")


# connector create

def connector_create(args):
    if not args.RNID:
        parser.error('no Remote Network ID passed')
    if not args.CONNNAME:
        parser.error('no Connector Name passed')
    if not args.NOTIFICATION:
        parser.error('no flag for notifications passed')
    isOK,Value = GenericValidators.checkStringAsBool(args.NOTIFICATION)
    if not isOK:
        parser.error('wrong value passed for parameter updateNotifications (true or false)')
    else:
        args.NOTIFICATION=Value
    ConnectorsLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.CONNNAME,args.RNID,args.NOTIFICATION)

# connector create
connector_create_parser = connector_subparsers.add_parser('create')
connector_create_parser.set_defaults(func=connector_create)
connector_create_parser.add_argument('-i','--networkid',type=str,default="", help='Remote Network ID', dest="RNID")
connector_create_parser.add_argument('-c','--connname',type=str,default="", help='Connector Name', dest="CONNNAME")
connector_create_parser.add_argument('-s','--sendnotifications',type=str,default="true", help='true or false', dest="NOTIFICATION")

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


# user <update role>
def user_update_role(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ROLE:
        parser.error('no role passed') 
    isOK, role = UserValidators.ValidateRole(args.ROLE)
    if not isOK:
        parser.error('role passed in not valid: '+str(role))

    UsersLogics.update_role(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,role)

# user update role
user_role_parser = user_subparsers.add_parser('role')
user_role_parser.set_defaults(func=user_update_role)
user_role_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
user_role_parser.add_argument('-r','--role',type=str,default="", help='ADMIN, DEVOPS, SUPPORT or MEMBER', dest="ROLE")


# user <create>
def user_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')

    if not args.LNAME:
        parser.error('no last name passed')

    if not args.EMAIL:
        parser.error('no email passed')

    if not args.ROLE:
        parser.error('no role passed') 
    
    isOK, role = UserValidators.ValidateRole(args.ROLE)
    if not isOK:
        parser.error('role passed in not valid: '+str(role))
    
    isOK,Value = GenericValidators.checkStringAsBool(args.SENDINVITE)
    if not isOK:
        parser.error('wrong value passed for "sendinvite" (true or false)')
    else:
        args.SENDINVITE=Value

    if not args.SESSIONNAME:
        parser.error('no session name passed')

    UsersLogics.create_user(args.OUTPUTFORMAT,args.SESSIONNAME,args.EMAIL,args.FNAME,args.LNAME,role,args.SENDINVITE)

# user create
user_role_parser = user_subparsers.add_parser('create')
user_role_parser.set_defaults(func=user_create)
user_role_parser.add_argument('-e','--email',type=str,default="", help='email address of the new user', dest="EMAIL")
user_role_parser.add_argument('-f','--firstname',type=str,default="", help='first name of the new user', dest="FNAME")
user_role_parser.add_argument('-l','--lastname',type=str,default="", help='last name of the new user', dest="LNAME")
user_role_parser.add_argument('-r','--role',type=str,default="", help='ADMIN, DEVOPS, SUPPORT or MEMBER', dest="ROLE")
user_role_parser.add_argument('-s','--sendinvite',type=str,default="True", help='send email invite (True or False (default: True))', dest="SENDINVITE")

# user <delete>
def user_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    UsersLogics.delete_user(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# user delete
user_delete_parser = user_subparsers.add_parser('delete')
user_delete_parser.set_defaults(func=user_delete)
user_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# user <update state>
def user_update_state(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    isOK,Value = UserValidators.ValidateState(args.STATE)
    if not isOK:
        parser.error('wrong value passed for "state"')

    UsersLogics.update_user_state(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.STATE)

# user update state
user_update_state_parser = user_subparsers.add_parser('state')
user_update_state_parser.set_defaults(func=user_update_state)
user_update_state_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
user_update_state_parser.add_argument('-s','--state',type=str,default="", help='state of user [ACTIVE, DISABLED]', dest="STATE")


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
    GroupsLogics.add_resources_to_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# group addResources
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

# group <addUsers>

def group_add_users(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.USERIDS != []:
        AllIDs = args.USERIDS.split(",")
        args.USERIDS = AllIDs
    GroupsLogics.add_users_to_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.USERIDS)

# group addUsers
group_addusers_parser = group_subparsers.add_parser('addUsers')
group_addusers_parser.set_defaults(func=group_add_users)
group_addusers_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_addusers_parser.add_argument('-u','--userids',type=str,default=[], help='list of User IDs, ex: "id1","id2"', dest="USERIDS")

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
    GroupsLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMNAME,args.USERIDS,args.RESOURCEIDS, args.POLICYID)

# group create
group_create_parser = group_subparsers.add_parser('create')
group_create_parser.set_defaults(func=group_create)
group_create_parser.add_argument('-g','--groupname',type=str,default="", help='group name', dest="ITEMNAME")
group_create_parser.add_argument('-u','--userids',type=str,default=[], help='list of User IDs, ex: "id1","id2"', dest="USERIDS")
group_create_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESOURCEIDS")
group_create_parser.add_argument('-p','--securitypolicyid',type=str,default=[], help='default security policy ID for group', dest="POLICYID")

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

# group <assignPolicy>

def group_assign_policy_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed [-g <group id>]')
    if not args.POLICYID:
        parser.error('no policy ID passed [-p <security policy id>]')
    GroupsLogics.assign_policy_to_group(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.POLICYID)

# group assignPolicy
group_assignpolicy_parser = group_subparsers.add_parser('assignPolicy')
group_assignpolicy_parser.set_defaults(func=group_assign_policy_resources)
group_assignpolicy_parser.add_argument('-g','--groupid',type=str,default="", help='group id', dest="ITEMID")
group_assignpolicy_parser.add_argument('-p','--policyid',type=str,default="", help='policy id', dest="POLICYID")

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
resource_create_parser.add_argument('-p','--policyid',type=str,default="", help='security policy id', dest="POLICYID")
resource_create_parser.add_argument('-g','--groupids',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")
resource_create_parser.add_argument('-i','--icmp',type=bool,default=False, help='(Optional) Disallow ICMP Protocol', dest="DISALLOWICMP")
resource_create_parser.add_argument('-t','--tcppolicy',type=str,default="ALLOW_ALL", help='(Optional) <ALLOW_ALL,RESTRICTED>, Default: ALLOW_ALL', dest="TCPPOLICY")
resource_create_parser.add_argument('-c','--tcprange',type=str,default="[]", help='(Optional) <[[a,b],[c,d],..]>, Default: [], ex:[[22-50],[443,443],[654-987]]', dest="TCPRANGE")
resource_create_parser.add_argument('-u','--udppolicy',type=str,default="ALLOW_ALL", help='(Optional) <ALLOW_ALL,RESTRICTED>, Default: ALLOW_ALL', dest="UDPPOLICY")
resource_create_parser.add_argument('-d','--udprange',type=str,default="[]", help='(Optional) <[[a,b],[c,d],..]>, Default: [], ex:[[22-50],[443,443],[654-987]]', dest="UDPRANGE")

# resource <delete>

def resource_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    ResourcesLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# resource delete
resource_delete_parser = resource_subparsers.add_parser('delete')
resource_delete_parser.set_defaults(func=resource_delete)
resource_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


# resource <assign_network>

def resource_assign_network(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.NETWORKID:
        parser.error('no item ID passed')

    ResourcesLogics.assign_network_to_resource(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.NETWORKID)

# resource assign network
resource_assignnetwork_parser = resource_subparsers.add_parser('assignNetwork')
resource_assignnetwork_parser.set_defaults(func=resource_assign_network)
resource_assignnetwork_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
resource_assignnetwork_parser.add_argument('-n','--networkid',type=str,default="", help='remote network id', dest="NETWORKID")


# resource <visibility>

def resource_toggle_visibility(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ISVISIBLE:
        parser.error('no value for visibility passed')
    isOK,Value = GenericValidators.checkStringAsBool(args.ISVISIBLE)
    if not isOK:
        parser.error('wrong value passed for parameter visibility (true or false)')
    else:
        args.ISVISIBLE=Value

    ResourcesLogics.update_visibility(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.ISVISIBLE)

# resource visibility
resource_togglevisibility_parser = resource_subparsers.add_parser('visibility')
resource_togglevisibility_parser.set_defaults(func=resource_toggle_visibility)
resource_togglevisibility_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
resource_togglevisibility_parser.add_argument('-v','--value',type=str, default="True", help='True or False (default: True)', dest="ISVISIBLE")

# resource <address update>

def resource_update_address(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ADDRESS:
        parser.error('no value for address passed')

    ResourcesLogics.update_address(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.ADDRESS)

# resource address update
resource_updateaddress_parser = resource_subparsers.add_parser('address')
resource_updateaddress_parser.set_defaults(func=resource_update_address)
resource_updateaddress_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
resource_updateaddress_parser.add_argument('-a','--address',type=str, default="", help='CIDR Block / IP / FQDN', dest="ADDRESS")

# resource <alias update>

def resource_update_alias(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ALIAS:
        parser.error('no value for alias passed')

    ResourcesLogics.update_alias(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.ALIAS)

# resource alias update
resource_updatealias_parser = resource_subparsers.add_parser('alias')
resource_updatealias_parser.set_defaults(func=resource_update_alias)
resource_updatealias_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
resource_updatealias_parser.add_argument('-a','--alias',type=str, default="", help='alias', dest="ALIAS")

# resource <policy update>
def resource_update_policy(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.POLICY:
        parser.error('no value for policy passed')

    ResourcesLogics.update_policy(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.POLICY)

# resource policy update
resource_updatepolicy_parser = resource_subparsers.add_parser('policy')
resource_updatepolicy_parser.set_defaults(func=resource_update_policy)
resource_updatepolicy_parser.add_argument('-i','--itemid',type=str,default="", help='resource id', dest="ITEMID")
resource_updatepolicy_parser.add_argument('-p','--policyid',type=str, default="", help='security policy id', dest="POLICY")


# resource <access remove>
def resource_access_remove(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no resource ID passed')
    if not args.GROUPID:
        parser.error('no value(s) for group or service account id passed')

    ResourcesLogics.access_remove(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPID)

access_remove_description = """
Given a Resource, remove Groups' and Service Accounts' access to the Resource. Any existing relationships outside what get specified here will remain in place.

Example Usage: tgcli -s [session] resource access_remove -i RESOURCEID -g GROUPID1[,GROUPID2,SERVICEACCOUNTID1,ID2 .. if applicable] 
"""

# resource access_remove
resource_access_remove_parser = resource_subparsers.add_parser('access_remove',description=access_remove_description, formatter_class=RawFormatter)
resource_access_remove_parser.set_defaults(func=resource_access_remove)
resource_access_remove_parser.add_argument('-i','--itemid',type=str,default="", help='resource id', dest="ITEMID")
resource_access_remove_parser.add_argument('-g','--groupid',type=str, default="", help='group id(s) [multiple ids separated by commas ie. id1,id2]', dest="GROUPID")




# resource <access_set>
def resource_access_set(args):
    policySplit = groupsSplit = ''
    if args.GROUPID:
        groupsSplit = args.GROUPID.split(',')
    if args.POLICYID:
        policySplit = args.POLICYID.split(',')
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no resource ID passed')
    if (args.GROUPID and not args.POLICYID):
        parser.error('you cant have a group id with no policy id');
    if not args.GROUPID and not args.SERVICEID:
        parser.error('no value(s) for group id (-g [group id]) or service account ([-s [service account id]) passed')
    if args.SERVICEID and args.POLICYID and not args.GROUPID:
        parser.error('you cannot specify a security policy when adding access for a service account. Please do not use the -p flag if you\'re only adding access for service accounts.')
    if len(policySplit) > 1 and len(groupsSplit) != len(policySplit):
        parser.error('you have ' + str(len(groupsSplit)) + ' groups but ' + str(len(policySplit)) + ' policies. You must have a single policy or ' + str(len(groupsSplit)) + ' policies to use this function. (see help -h)')
    ResourcesLogics.access_set(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPID,args.SERVICEID,args.POLICYID)

access_set_description = """
Given a Resource, set which Groups or Service Account has access to the Resource and, for a Group, which Security Policy they use. Any existing Group or Service Account connections will be removed.

Example Usage: tgcli -s [session] resource access_set -i RESOURCEID -g GROUPID1[,ID2,ID3 ... if applicable] -p POLICYID1[,ID2,ID3 ... if applicable] -s SERVICEACCOUNTID1[,ID2,ID3 ... if applicable] 

** Note on policies: If only one policy ID is passed, it will be used for all groups specified. If multiple policies are passed, you must have a matching number of groups and policies, and the policies will be applied to the corresponding group (ie GROUPID1 will get POLICYID1, GROUPID2 will get POLICYID2, etc).
If you do not have an equal count of group and policy IDs, the command will fail. Service accounts cannot have policies attached to them and do not require additional input.
"""

# resource access_set
resource_access_set_parser = resource_subparsers.add_parser('access_set',description=access_set_description, formatter_class=RawFormatter)
resource_access_set_parser.set_defaults(func=resource_access_set)
resource_access_set_parser.add_argument('-i','--itemid',type=str,default="", help='resource id', dest="ITEMID")
resource_access_set_parser.add_argument('-g','--group',type=str, default="", help='group id', dest="GROUPID")
resource_access_set_parser.add_argument('-p','--policy',type=str, default="", help='security policy id', dest="POLICYID")
resource_access_set_parser.add_argument('-s','--service',type=str, default="", help='service account id', dest="SERVICEID")


# resource <access add>
def resource_access_add(args):
    policySplit = groupsSplit = ''
    if args.GROUPID:
        groupsSplit = args.GROUPID.split(',')
    if args.POLICYID:
        policySplit = args.POLICYID.split(',')
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no resource ID passed')
    if (args.GROUPID and not args.POLICYID):
        parser.error('you cant have a group id with no policy id');
    if not args.GROUPID and not args.SERVICEID:
        parser.error('no value(s) for group id (-g [group id]) or service account ([-s [service account id]) passed')
    if args.SERVICEID and args.POLICYID and not args.GROUPID:
        parser.error('you cannot specify a security policy when adding access for a service account. Please do not use the -p flag if you\'re only adding access for service accounts.')
    if len(policySplit) > 1 and len(groupsSplit) != len(policySplit):
        parser.error('you have ' + str(len(groupsSplit)) + ' groups but ' + str(len(policySplit)) + ' policies. You must have a single policy or ' + str(len(groupsSplit)) + ' policies to use this function. (see help -h)')
  

    ResourcesLogics.access_add(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPID,args.SERVICEID,args.POLICYID)

# resource add access
access_add_description = """
Given a Resource, add Groups or Service Accounts with access to the Resource and, for Groups, define which Security Policy they use. This is additive and will not remove any existing relationships for Groups/Service Accounts not used here.

Example Usage: tgcli -s [session] resource access_add -i RESOURCEID -g GROUPID1[,ID2,ID3 ... if applicable] -p POLICYID1[,ID2,ID3 ... if applicable] -s SERVICEACCOUNTID1[,ID2,ID3 ... if applicable] 

** Note on policies: If only one policy ID is passed, it will be used for all groups specified. If multiple policies are passed, you must have a matching number of groups and policies, and the policies will be applied to the corresponding group (ie GROUPID1 will get POLICYID1, GROUPID2 will get POLICYID2, etc).
If you do not have an equal count of group and policy IDs, the command will fail. Service accounts cannot have policies attached to them and do not require additional input.
"""
resource_access_add_parser = resource_subparsers.add_parser('access_add', description=access_add_description, formatter_class=RawFormatter)
resource_access_add_parser.set_defaults(func=resource_access_add)
resource_access_add_parser.add_argument('-i','--itemid',type=str,default="", help='resource id', dest="ITEMID")
resource_access_add_parser.add_argument('-g','--group',type=str, default="", help='group id(s)', dest="GROUPID")
resource_access_add_parser.add_argument('-p','--policy',type=str, default="", help='security policy id(s)', dest="POLICYID")
resource_access_add_parser.add_argument('-s','--service',type=str, default="", help='service account id', dest="SERVICEID")

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

# network <create>

def network_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.NAME:
        parser.error('name not passed')
    isOK,Value = GenericValidators.checkStringAsBool(args.ISACTIVE)
    if not isOK:
        parser.error('wrong value passed for parameter updateNotifications (true or false)')
    isSuccess,checked_location = RNValidators.ValidateRNLocation(args.LOCATION)
    if not isSuccess:
        parser.error(str(args.LOCATION)+" is incorrect, possible values are: "+checked_location)

    RemoteNetworksLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.NAME,checked_location,Value)

# network create
network_create_parser = network_subparsers.add_parser('create')
network_create_parser.set_defaults(func=network_create)
network_create_parser.add_argument('-n','--name',type=str,default="", help='Remote Network name', dest="NAME")
network_create_parser.add_argument('-l','--location',type=str,default="OTHER", help='location, possible values: [OTHER, AWS, AZURE, GOOGLE_CLOUD, ON_PREMISE]', dest="LOCATION")
network_create_parser.add_argument('-a','--active',type=str,default="", help='Create the Remote Network in active or inactive state', dest="ISACTIVE")


# network <delete>

def network_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ID:
        parser.error('id not passed')

    RemoteNetworksLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ID)

# network delete
network_delete_parser = network_subparsers.add_parser('delete')
network_delete_parser.set_defaults(func=network_delete)
network_delete_parser.add_argument('-i','--id',type=str,default="", help='item id', dest="ID")


#####
# Service Account Parser
# account <list>
#####

# account commands
account_parser = subparsers.add_parser('account')
account_subparsers = account_parser.add_subparsers()

def account_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    ServiceAccountsLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

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


# account <create>

def account_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMNAME:
        parser.error('no item name passed')
    if args.RESOURCEIDS != []:
        AllIDs = args.RESOURCEIDS.split(",")
        args.RESOURCEIDS = AllIDs
    ServiceAccountsLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMNAME,args.RESOURCEIDS)

# account Create
account_create_parser = account_subparsers.add_parser('create')
account_create_parser.set_defaults(func=account_create)
account_create_parser.add_argument('-n','--name',type=str,default="", help='account name', dest="ITEMNAME")
account_create_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESOURCEIDS")

# account <delete>

def account_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    ServiceAccountsLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# account delete
account_delete_parser = account_subparsers.add_parser('delete')
account_delete_parser.set_defaults(func=account_delete)
account_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")


# account <addResources>

def account_add_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.RESIDS != []:
        AllIDs = args.RESIDS.split(",")
        args.RESIDS = AllIDs
    ServiceAccountsLogics.add_resources_to_saccount(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# account addResources
account_addresources_parser = account_subparsers.add_parser('addResources')
account_addresources_parser.set_defaults(func=account_add_resources)
account_addresources_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
account_addresources_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESIDS")

# account <removeResources>

def account_remove_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.RESIDS != []:
        AllIDs = args.RESIDS.split(",")
        args.RESIDS = AllIDs
    ServiceAccountsLogics.remove_resources_from_saccount(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.RESIDS)

# account removeResources
account_removeresources_parser = account_subparsers.add_parser('removeResources')
account_removeresources_parser.set_defaults(func=account_remove_resources)
account_removeresources_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
account_removeresources_parser.add_argument('-r','--resourceids',type=str,default=[], help='list of Resource IDs, ex: "id1","id2"', dest="RESIDS")


#####
# S. Account Key Parser
# key <cmd>
#####

# saccount key commands
saccount_key_parser = subparsers.add_parser('key')
saccount_key_subparsers = saccount_key_parser.add_subparsers()

# saccount key show
def key_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    SAccountKeysLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# saccount key show
saccount_key_show_parser = saccount_key_subparsers.add_parser('show')
saccount_key_show_parser.set_defaults(func=key_show)
saccount_key_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# saccount key create
def saccount_key_create(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMNAME:
        parser.error('no item name passed')
    if not args.SACCID:
        parser.error('no service account id passed') 
    isOK, ProcessedExp = ServiceAccountKeyValidators.ValidateExpiration(args.EXP)
    if not isOK:
        parser.error(ProcessedExp)

    SAccountKeysLogics.item_create(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMNAME,args.SACCID,ProcessedExp)

# saccount key Create
saccount_key_create_parser = saccount_key_subparsers.add_parser('create')
saccount_key_create_parser.set_defaults(func=saccount_key_create)
saccount_key_create_parser.add_argument('-n','--name',type=str,default="", help='account name', dest="ITEMNAME")
saccount_key_create_parser.add_argument('-i','--saccountid',type=str,default=[], help='Service Account Id', dest="SACCID")
saccount_key_create_parser.add_argument('-e','--expiration',type=str,default=1, help='Expiration (number of days between 0 to 365)', dest="EXP")

# saccount key <delete>

def saccount_key_delete(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    SAccountKeysLogics.item_delete(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# saccount key delete
saccount_key_delete_parser = saccount_key_subparsers.add_parser('delete')
saccount_key_delete_parser.set_defaults(func=saccount_key_delete)
saccount_key_delete_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# saccount key <revoke>

def saccount_key_revoke(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')

    SAccountKeysLogics.item_revoke(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# saccount revoke
saccount_key_revoke_parser = saccount_key_subparsers.add_parser('revoke')
saccount_key_revoke_parser.set_defaults(func=saccount_key_revoke)
saccount_key_revoke_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# saccount key <rename>

def saccount_key_rename(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if not args.ITEMNAME:
        parser.error('no item name passed')

    SAccountKeysLogics.item_rename(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.ITEMNAME)

# saccount rename
saccount_key_rename_parser = saccount_key_subparsers.add_parser('rename')
saccount_key_rename_parser.set_defaults(func=saccount_key_rename)
saccount_key_rename_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")
saccount_key_rename_parser.add_argument('-n','--itemname',type=str,default="", help='new item name', dest="ITEMNAME")


#####
# Security Policies Parser
# policy <list>
#####

def secpol_list(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    SecPoliciesLogics.item_list(args.OUTPUTFORMAT,args.SESSIONNAME)

# Device commands
secpol_parser = subparsers.add_parser('policy')
secpol_subparsers = secpol_parser.add_subparsers()

# policy list
policy_list_parser = secpol_subparsers.add_parser('list')
policy_list_parser.set_defaults(func=secpol_list)

# policy <show>
def secpol_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no policy ID passed')

    SecPoliciesLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID)

# policy show
policy_show_parser = secpol_subparsers.add_parser('show')
policy_show_parser.set_defaults(func=secpol_show)
policy_show_parser.add_argument('-i','--itemid',type=str,default="", help='item id', dest="ITEMID")

# the following logic is no longer applicable since Policies are now applied to Resources and not Groups
'''
# policy <addGroups>
def secpol_add_groups(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.GROUPIDS != []:
        AllIDs = args.GROUPIDS.split(",")
        args.GROUPIDS = AllIDs
    SecPoliciesLogics.add_groups_to_policy(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPIDS)

# policy addGroups
policy_addgroups_parser = secpol_subparsers.add_parser('addGroups')
policy_addgroups_parser.set_defaults(func=secpol_add_groups)
policy_addgroups_parser.add_argument('-i','--policyid',type=str,default="", help='policy id', dest="ITEMID")
policy_addgroups_parser.add_argument('-g','--groupids',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")

# policy <removeGroups>

def secpol_remove_groups(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.GROUPIDS != []:
        AllIDs = args.GROUPIDS.split(",")
        args.GROUPIDS = AllIDs
    SecPoliciesLogics.remove_groups_from_policy(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPIDS)

# policy removeGroups
policy_addgroups_parser = secpol_subparsers.add_parser('removeGroups')
policy_addgroups_parser.set_defaults(func=secpol_remove_groups)
policy_addgroups_parser.add_argument('-i','--policyid',type=str,default="", help='policy id', dest="ITEMID")
policy_addgroups_parser.add_argument('-g','--groupids',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")

# policy <setGroups>

def secpol_set_groups(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.ITEMID:
        parser.error('no item ID passed')
    if args.GROUPIDS != []:
        AllIDs = args.GROUPIDS.split(",")
        args.GROUPIDS = AllIDs
    SecPoliciesLogics.set_groups_for_policy(args.OUTPUTFORMAT,args.SESSIONNAME,args.ITEMID,args.GROUPIDS)

# policy setGroups
policy_setgroups_parser = secpol_subparsers.add_parser('setGroups')
policy_setgroups_parser.set_defaults(func=secpol_set_groups)
policy_setgroups_parser.add_argument('-i','--policyid',type=str,default="", help='policy id', dest="ITEMID")
policy_setgroups_parser.add_argument('-g','--groupids',type=str,default=[], help='list of Group IDs, ex: "id1","id2"', dest="GROUPIDS")
'''


#####
#
# DNS Security Parser
# 
#####

# DNS Security commands
## dnssec_parser = subparsers.add_parser('dnssec')
## dnssec_subparsers = dnssec_parser.add_subparsers()

# DNS Security <show>

def dnssec_show(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')

    DNSSecLogics.item_show(args.OUTPUTFORMAT,args.SESSIONNAME)

# DNS Security show
## dnssec_show_parser = dnssec_subparsers.add_parser('show')
## dnssec_show_parser.set_defaults(func=dnssec_show)

# DNS Security <SetAllowList>

def dnssec_allow_list_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.CSVDOMAINS:
        parser.error('no Domains passed')
    Domains = args.CSVDOMAINS.split(",")

    DNSSecLogics.set_allow_list(args.OUTPUTFORMAT,args.SESSIONNAME,Domains)

# DNS Security <SetAllowList>
## dnssec_allowlist_parser = dnssec_subparsers.add_parser('setAllowList')
## dnssec_allowlist_parser.set_defaults(func=dnssec_allow_list_resources)
## dnssec_allowlist_parser.add_argument('-d','--domains',type=str,default="", help='CSV list of domains', dest="CSVDOMAINS")

# DNS Security <SetDenyList>

def dnssec_deny_list_resources(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.CSVDOMAINS:
        parser.error('no Domains passed')

    Domains = args.CSVDOMAINS.split(",")

    DNSSecLogics.set_deny_list(args.OUTPUTFORMAT,args.SESSIONNAME,Domains)

# DNS Security <SetAllowList>
## dnssec_denylist_parser = dnssec_subparsers.add_parser('setDenyList')
## dnssec_denylist_parser.set_defaults(func=dnssec_deny_list_resources)
## dnssec_denylist_parser.add_argument('-d','--domains',type=str,default="", help='CSV list of domains', dest="CSVDOMAINS")

#####
# Mapping Parser
# key <cmd>
#####

# mappings commands
mappings_parser = subparsers.add_parser('mappings')
mappings_subparsers = mappings_parser.add_subparsers()

# get user based mapping
def user_to_resource_mappings(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')
    if not args.EMAILADDR:
        parser.error('no email address passed')

    MappingsLogics.get_user_mappings(args.OUTPUTFORMAT,args.SESSIONNAME,args.EMAILADDR,args.FQDN)

mappings_user_res_parser = mappings_subparsers.add_parser('user-resource')
mappings_user_res_parser.set_defaults(func=user_to_resource_mappings)
mappings_user_res_parser.add_argument('-e','--email',type=str,default="", help='user email address', dest="EMAILADDR")
mappings_user_res_parser.add_argument('-f','--fqdn',type=str,default="", help='[optional] FQDN to use and analyze against available resources', dest="FQDN")


# get user - RN based mapping
def user_to_rn_mappings(args):
    if not args.SESSIONNAME:
        parser.error('no session name passed')

    MappingsLogics.get_user_rn_mapping(args.OUTPUTFORMAT,args.SESSIONNAME)

# saccount key show
mappings_user_res_parser = mappings_subparsers.add_parser('user-network')
mappings_user_res_parser.set_defaults(func=user_to_rn_mappings)


DebugLevels = ["ERROR","DEBUG","WARNING","INFO"]
if __name__ == '__main__':
    args = parser.parse_args()
    if not args.DEBUGLEVEL.upper() in DebugLevels:
        args.DEBUGLEVEL = DebugLevels[0]

    logging.basicConfig(level=getattr(logging, args.DEBUGLEVEL.upper()))
    #
    args.func(args) 
    #try:
    #   args.func(args) 
    #except Exception as e:
        #logging.error(e)
    #    print("general error, please check commands & parameters. Hint: Use -h")
    #    print(e)
