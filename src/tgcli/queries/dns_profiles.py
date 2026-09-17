"""GraphQL queries for DNS Filtering profiles.

Distinct from `queries/dnssec.py` and `queries/policies.py`:
DnsFilteringProfile is its own GraphQL type (multiple profiles per tenant,
each assigned to a set of Groups) -- not the single implicit profile the
legacy `dnssec` commands assume, and not a Resource/Security Policy.
"""

from __future__ import annotations

LIST_DNS_PROFILES = """
query listDnsProfiles {
  dnsFilteringProfiles {
    id
    name
    priority
  }
}
"""

SHOW_DNS_PROFILE = """
query getDnsProfile($itemID: ID!) {
  dnsFilteringProfile(id: $itemID) {
    id
    name
    priority
    fallbackMethod
    allowedDomains
    deniedDomains
    groups {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""
