"""GraphQL queries and mutations for access requests."""

from __future__ import annotations

LIST_ACCESS_REQUESTS = """
query listAccessRequests($cursor: String!) {
  accessRequests(after: $cursor, first: null) {
    totalCount
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
mutation approveAccessRequest($id: ID!) {
  accessRequestApprove(id: $id) {
    ok
    error
  }
}
"""

REJECT_ACCESS_REQUEST = """
mutation rejectAccessRequest($id: ID!) {
  accessRequestReject(id: $id) {
    ok
    error
  }
}
"""
