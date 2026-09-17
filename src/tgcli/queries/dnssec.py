"""GraphQL queries and mutations for DNS security (filtering).

Legacy single-profile commands, kept for backward-compatible command names.
Twingate's API no longer has an implicit default profile or the old
dnsFiltering{Allowed,Denied}DomainsSet mutations -- every profile is now
identified by ID (see `queries/dns_profiles.py` for full multi-profile
support: listing profiles and their assigned groups).
"""

from __future__ import annotations

SHOW_DNS_PROFILE = """
query CLI_GetDNSFilteringProfile($itemID: ID!) {
  dnsFilteringProfile(id: $itemID) {
    id
    allowedDomains
    deniedDomains
  }
}
"""

SET_ALLOWED_DOMAINS = """
mutation CLI_SetDNSAllowedDomains($itemID: ID!, $domains: [String!]!) {
  dnsFilteringProfileUpdate(id: $itemID, allowedDomains: $domains) {
    ok
    error
    entity {
      id
      allowedDomains
    }
  }
}
"""

SET_DENIED_DOMAINS = """
mutation CLI_SetDNSDeniedDomains($itemID: ID!, $domains: [String!]!) {
  dnsFilteringProfileUpdate(id: $itemID, deniedDomains: $domains) {
    ok
    error
    entity {
      id
      deniedDomains
    }
  }
}
"""
