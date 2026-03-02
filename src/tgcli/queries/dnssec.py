"""GraphQL queries and mutations for DNS security (filtering)."""

from __future__ import annotations

SHOW_DNS_PROFILE = """
query CLI_GetDNSFilteringProfile {
  dnsFilteringProfile {
    id
    allowedDomains
    deniedDomains
  }
}
"""

SET_ALLOWED_DOMAINS = """
mutation CLI_SetDNSAllowedDomains($domains: [String!]!) {
  dnsFilteringAllowedDomainsSet(domains: $domains) {
    ok
    error
  }
}
"""

SET_DENIED_DOMAINS = """
mutation CLI_SetDNSdeniedDomains($domains: [String!]!) {
  dnsFilteringDeniedDomainsSet(domains: $domains) {
    ok
    error
  }
}
"""
