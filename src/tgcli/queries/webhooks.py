"""GraphQL queries and mutations for webhooks."""

from __future__ import annotations

LIST_WEBHOOKS = """
query listWebhooks($cursor: String!) {
  webhooks(after: $cursor, first: null) {
    totalCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        name
        url
        lastSuccessfulAt
        lastErrorAt
      }
    }
  }
}
"""

SHOW_WEBHOOK = """
query getWebhook($itemID: ID!) {
  webhook(id: $itemID) {
    id
    name
    url
    lastSuccessfulAt
    lastErrorAt
  }
}
"""

CREATE_WEBHOOK = """
mutation createWebhook($name: String!, $url: String!) {
  webhookCreate(name: $name, url: $url) {
    ok
    error
    entity {
      id
      name
      url
    }
  }
}
"""

DELETE_WEBHOOK = """
mutation deleteWebhook($id: ID!) {
  webhookDelete(id: $id) {
    ok
    error
  }
}
"""

UPDATE_WEBHOOK = """
mutation updateWebhook($id: ID!, $name: String, $url: String) {
  webhookUpdate(id: $id, name: $name, url: $url) {
    ok
    error
    entity {
      id
      name
      url
    }
  }
}
"""
