import requests
import json
import sys
import os

sys.path.insert(1, './libs')
sys.path.insert(1, './transformers')
import GenericTransformers
import DevicePostureTransformers
import StdAPIUtils


def get_posture_list_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"cursor": JsonData['cursor']}

    Body = """
    query ListDevicePostureChecks($cursor: String!) {
        devicePostureChecks(after: $cursor) {
            pageInfo {
                endCursor
                hasNextPage
            }
            edges {
                node {
                    id
                    name
                    description
                    type
                    action
                    status
                    createdAt
                    updatedAt
                }
            }
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def get_posture_show_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"checkID": JsonData['itemid']}

    Body = """
    query GetDevicePostureCheck($checkID: ID!) {
        devicePostureCheck(id: $checkID) {
            id
            name
            description
            type
            action
            status
            createdAt
            updatedAt
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def get_posture_create_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {
        "name": JsonData['name'],
        "description": JsonData.get('description', ''),
        "type": JsonData['type'],
        "action": JsonData['action'],
    }

    Body = """
    mutation CreateDevicePostureCheck(
        $name: String!,
        $description: String,
        $type: DevicePostureCheckType!,
        $action: DevicePostureCheckAction!
    ) {
        devicePostureCheckCreate(
            name: $name,
            description: $description,
            type: $type,
            action: $action
        ) {
            ok
            error
            entity {
                id
                name
                description
                type
                action
                status
            }
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def get_posture_update_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"checkID": JsonData['itemid']}

    if JsonData.get('name'):
        variables['name'] = JsonData['name']
    if JsonData.get('description') is not None:
        variables['description'] = JsonData['description']
    if JsonData.get('action'):
        variables['action'] = JsonData['action']
    if JsonData.get('status'):
        variables['status'] = JsonData['status']

    Body = """
    mutation UpdateDevicePostureCheck(
        $checkID: ID!,
        $name: String,
        $description: String,
        $action: DevicePostureCheckAction,
        $status: DevicePostureCheckStatus
    ) {
        devicePostureCheckUpdate(
            id: $checkID,
            name: $name,
            description: $description,
            action: $action,
            status: $status
        ) {
            ok
            error
            entity {
                id
                name
                description
                type
                action
                status
            }
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def get_posture_delete_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"checkID": JsonData['itemid']}

    Body = """
    mutation DeleteDevicePostureCheck($checkID: ID!) {
        devicePostureCheckDelete(id: $checkID) {
            ok
            error
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def item_list(outputFormat, sessionname):
    ListOfResponses = []
    hasMorePages = True
    Cursor = "0"
    while hasMorePages:
        j = StdAPIUtils.generic_api_call_handler(sessionname, get_posture_list_resources, {'cursor': Cursor})
        hasMorePages, Cursor = GenericTransformers.CheckIfMorePages(j, 'devicePostureChecks')
        ListOfResponses.append(j['data']['devicePostureChecks']['edges'])
    output, r = StdAPIUtils.format_output(ListOfResponses, outputFormat, DevicePostureTransformers.GetListAsCsv)
    print(output)


def item_show(outputFormat, sessionname, itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname, get_posture_show_resources, {'itemid': itemid})
    output, r = StdAPIUtils.format_output(j, outputFormat, DevicePostureTransformers.GetShowAsCsv)
    print(output)


def item_create(outputFormat, sessionname, name, check_type, action, description):
    j = StdAPIUtils.generic_api_call_handler(
        sessionname, get_posture_create_resources,
        {'name': name, 'type': check_type, 'action': action, 'description': description}
    )
    output, r = StdAPIUtils.format_output(j, outputFormat, DevicePostureTransformers.GetCreateAsCsv)
    print(output)


def item_update(outputFormat, sessionname, itemid, name, action, status, description):
    j = StdAPIUtils.generic_api_call_handler(
        sessionname, get_posture_update_resources,
        {'itemid': itemid, 'name': name, 'action': action, 'status': status, 'description': description}
    )
    output, r = StdAPIUtils.format_output(j, outputFormat, DevicePostureTransformers.GetUpdateAsCsv)
    print(output)


def item_delete(outputFormat, sessionname, itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname, get_posture_delete_resources, {'itemid': itemid})
    output, r = StdAPIUtils.format_output(j, outputFormat, DevicePostureTransformers.GetDeleteAsCsv)
    print(output)


def get_device_posture_resources(token, JsonData):
    Headers = StdAPIUtils.get_api_call_headers(token)
    api_call_type = "POST"
    variables = {"deviceID": JsonData['itemid']}

    Body = """
    query GetDevicePosture($deviceID: ID!) {
        devicePosture(id: $deviceID) {
            hardDriveEncryption {
                isSatisfied
                detected
            }
            screenLockPasscode {
                isSatisfied
                detected
            }
            firewall {
                isSatisfied
                detected
            }
            biometric {
                isSatisfied
                detected
            }
            antivirus {
                isSatisfied
                detected
            }
            osVersion {
                isSatisfied
                version
            }
            crowdstrike {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            jamf {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            kandji {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            inTune {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            sentinelOne {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            onePassword {
                isVerified
                failureReason
                expiredAt
                failureDetails
            }
            manualVerification {
                isVerified
                value
            }
        }
    }
    """
    return True, api_call_type, Headers, Body, variables


def device_posture_check(outputFormat, sessionname, itemid):
    j = StdAPIUtils.generic_api_call_handler(sessionname, get_device_posture_resources, {'itemid': itemid})
    output, r = StdAPIUtils.format_output(j, outputFormat, DevicePostureTransformers.GetDevicePostureAsCsv)
    print(output)
