"""GraphQL queries and mutations for access requests."""

from __future__ import annotations

LIST_ACCESS_REQUESTS = """
query listAccessRequests($cursor: String!, $filter: AccessRequestFilterInput) {
  accessRequests(after: $cursor, first: null, filter: $filter) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        id
        status
        reason
        requestedAt
        user {
          id
          email
        }
        resource {
          id
          name
        }
      }
    }
  }
}
"""

SHOW_ACCESS_REQUEST = """
query getAccessRequest($itemID: ID!) {
  accessRequest(id: $itemID) {
    id
    status
    reason
    requestedAt
    user {
      id
      email
    }
    resource {
      id
      name
    }
  }
}
"""

APPROVE_ACCESS_REQUEST = """
mutation approveAccessRequest($itemID: ID!) {
  accessRequestApprove(id: $itemID) {
    ok
    error
  }
}
"""

REJECT_ACCESS_REQUEST = """
mutation rejectAccessRequest($itemID: ID!) {
  accessRequestReject(id: $itemID) {
    ok
    error
  }
}
"""
