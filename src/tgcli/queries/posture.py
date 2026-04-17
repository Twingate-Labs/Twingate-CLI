"""GraphQL queries for device posture."""

from __future__ import annotations

DEVICE_POSTURE_CHECK = """
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
