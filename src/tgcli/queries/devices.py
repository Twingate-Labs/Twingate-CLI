"""GraphQL queries and mutations for devices and serial numbers."""

from __future__ import annotations

LIST_DEVICES = """
query listGroup($cursor: String!)
{
  devices(after: $cursor, first:null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        isTrusted
        osName
        deviceType
        lastFailedLoginAt
        lastSuccessfulLoginAt
        lastConnectedAt
        osVersion
        hardwareModel
        hostname
        username
        serialNumber
        user {
          firstName
          lastName
          email
        }
        activeState
        clientVersion
        manufacturerName
      }
    }
  }
}
"""

SHOW_DEVICE = """
query getDevice($deviceID: ID!) {
  device(id: $deviceID) {
    id
    name
    isTrusted
    osName
    deviceType
    lastFailedLoginAt
    lastSuccessfulLoginAt
    lastConnectedAt
    osVersion
    hardwareModel
    hostname
    username
    serialNumber
    user {
      firstName
      lastName
      email
    }
    activeState
    clientVersion
    manufacturerName
  }
}
"""

UPDATE_DEVICE_TRUST = """
mutation updateDeviceTrust($deviceID: ID!, $isTrusted: Boolean!) {
  deviceUpdate(id: $deviceID, isTrusted: $isTrusted) {
    ok
    error
    entity {
      id
      name
      isTrusted
      activeState
    }
  }
}
"""

BLOCK_DEVICE = """
mutation updateDevice($deviceID: ID!) {
  deviceBlock(id: $deviceID) {
    ok
    error
    entity {
      id
      name
      isTrusted
      activeState
    }
  }
}
"""

UNBLOCK_DEVICE = """
mutation updateDevice($deviceID: ID!) {
  deviceUnblock(id: $deviceID) {
    ok
    error
    entity {
      id
      name
      isTrusted
      activeState
    }
  }
}
"""

ARCHIVE_DEVICE = """
mutation updateDevice($deviceID: ID!) {
  deviceArchive(id: $deviceID) {
    ok
    error
    entity {
      id
      name
      isTrusted
      activeState
    }
  }
}
"""

LIST_SERIAL_NUMBERS = """
query PM_GetListOfSerialNumbers($cursor: String!) {
  serialNumbers(after: $cursor) {
    edges {
      node {
        id
        serialNumber
        createdAt
        matchedDevices {
          id
          name
        }
      }
    }
    pageInfo {
      endCursor
      hasNextPage
    }
  }
}
"""

ADD_SERIAL_NUMBERS = """
mutation PM_serialNumbersCreate($serialnums: [String!]!) {
  serialNumbersCreate(serialNumbers: $serialnums) {
    ok
    error
    entities {
      id
      createdAt
      serialNumber
      matchedDevices {
        id
        name
      }
    }
  }
}
"""

DELETE_SERIAL_NUMBERS = """
mutation PM_serialNumbersDelete($serialnums: [String!]!) {
  serialNumbersDelete(serialNumbers: $serialnums) {
    ok
    error
  }
}
"""

POSTURE_DEVICE = """
query getDevicePosture($deviceID: ID!) {
  devicePosture(id: $deviceID) {
      hardDriveEncryption { isSatisfied detected }
      screenLockPasscode  { isSatisfied detected }
      firewall            { isSatisfied detected }
      biometric           { isSatisfied detected }
      antivirus           { isSatisfied detected }
      osVersion           { isSatisfied version  }
      crowdstrike   { isVerified failureReason expiredAt failureDetails }
      jamf          { isVerified failureReason expiredAt failureDetails }
      kandji        { isVerified failureReason expiredAt failureDetails }
      inTune        { isVerified failureReason expiredAt failureDetails }
      sentinelOne   { isVerified failureReason expiredAt failureDetails }
      onePassword   { isVerified failureReason expiredAt failureDetails }
      manualVerification { isVerified value }
    
  }
}
"""
