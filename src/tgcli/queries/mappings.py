"""GraphQL queries for user-to-resource and user-to-network mapping analytics."""

from __future__ import annotations

LIST_USER_RN_MAPPINGS = """
query getUsers($cursor: String!) {
  users(after: $cursor) {
    edges {
      node {
        id
        firstName
        lastName
        email
        groups {
          edges {
            node {
              name
              resources {
                edges {
                  node {
                    id
                    name
                    remoteNetwork {
                      id
                      name
                    }
                  }
                }
              }
            }
          }
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

GET_USER_BY_EMAIL = """
query listUsers($userEmail: String!) {
  users(filter: {email: {eq: $userEmail}}) {
    edges {
      node {
        id
        firstName
        lastName
        email
        createdAt
        updatedAt
        state
        groups {
          edges {
            node {
              id
            }
          }
        }
      }
    }
    pageInfo {
      startCursor
      hasNextPage
    }
  }
}
"""

GET_GROUP_RESOURCES = """
query getGroup($cursor: String!, $groupID: ID!) {
  group(id: $groupID) {
    id
    name
    resources(after: $cursor) {
      edges {
        node {
          id
          name
          address {
            type
            value
          }
          remoteNetwork {
            id
            name
          }
          isActive
        }
      }
      pageInfo {
        endCursor
        hasNextPage
      }
    }
  }
}
"""
