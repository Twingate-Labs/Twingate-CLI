"""GraphQL queries and mutations for DNS security (filtering)."""

from __future__ import annotations

LIST_DNS_PROFILES = """
{
  dnsFilteringProfiles {
    id
    name
  }
}
"""

SHOW_DNS_PROFILE = """
query CLI_GetDNSFilteringProfile($id: ID!) {
  dnsFilteringProfile(id: $id) {
    id
    name
    allowedDomains
    deniedDomains
  }
}
"""

UPDATE_DNS_PROFILE = """
mutation CLI_UpdateDNSFilteringProfile($id: ID!, $allowedDomains: [String!], $deniedDomains: [String!]) {
  dnsFilteringProfileUpdate(id: $id, allowedDomains: $allowedDomains, deniedDomains: $deniedDomains) {
    ok
    error
    entity {
      id
      allowedDomains
      deniedDomains
    }
  }
}
"""

SET_ALLOWED_DOMAINS = UPDATE_DNS_PROFILE
SET_DENIED_DOMAINS = UPDATE_DNS_PROFILE
