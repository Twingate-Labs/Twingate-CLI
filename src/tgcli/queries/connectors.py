"""GraphQL queries and mutations for connectors."""

from __future__ import annotations

LIST_CONNECTORS = """
query listObj($cursor: String!) {
  connectors(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        state
        hostname
        version
        publicIP
        privateIPs
        lastHeartbeatAt
        createdAt
        updatedAt
        hasStatusNotificationsEnabled
      }
    }
  }
}
"""

SHOW_CONNECTOR = """
query getObj($itemID: ID!) {
  connector(id: $itemID) {
    id
    name
    state
    hostname
    version
    publicIP
    privateIPs
    lastHeartbeatAt
    hasStatusNotificationsEnabled
    remoteNetwork {
      id
      name
    }
  }
}
"""

CREATE_CONNECTOR = """
mutation connectorCreate($connName: String!, $remoteNetworkID: ID!, $statNotifications: Boolean) {
  connectorCreate(name: $connName, remoteNetworkId: $remoteNetworkID, hasStatusNotificationsEnabled: $statNotifications) {
    ok
    error
    entity {
      id
      name
      state
      lastHeartbeatAt
      hasStatusNotificationsEnabled
      remoteNetwork {
        id
        name
      }
    }
  }
}
"""

RENAME_CONNECTOR = """
mutation ObjRename($id: ID!, $name: String!) {
  connectorUpdate(id: $id, name: $name) {
    ok
    error
    entity {
      id
      name
      hasStatusNotificationsEnabled
    }
  }
}
"""

UPDATE_CONNECTOR_NOTIFICATIONS = """
mutation ObjUpd($id: ID!, $hasStatusNotificationsEnabled: Boolean!) {
  connectorUpdate(id: $id, hasStatusNotificationsEnabled: $hasStatusNotificationsEnabled) {
    ok
    error
    entity {
      id
      name
      hasStatusNotificationsEnabled
    }
  }
}
"""

GENERATE_CONNECTOR_TOKENS = """
mutation GetConnTokens($id: ID!) {
  connectorGenerateTokens(connectorId: $id) {
    ok
    error
    connectorTokens {
      accessToken
      refreshToken
    }
  }
}
"""
