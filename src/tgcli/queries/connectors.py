"""GraphQL queries and mutations for connectors."""

from __future__ import annotations

LIST_CONNECTORS = """
query listConnectors($cursor: String!, $filter: ConnectorFilterInput) {
  connectors(after: $cursor, first: null, filter: $filter) {
    totalCount
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
        remoteNetwork {
          id
          name
        }
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
mutation renameConnector($id: ID!, $name: String!) {
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
mutation updateConnectorNotifications($id: ID!, $hasStatusNotificationsEnabled: Boolean!) {
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

DELETE_CONNECTOR = """
mutation connectorDelete($id: ID!) {
  connectorDelete(id: $id) {
    ok
    error
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

HEALTH_CONNECTORS = """
{ connectors(first: null, after: "0") { totalCount edges { node { id state remoteNetwork { id } } } } }
"""
