"""GraphQL queries for DNS Filtering profiles.

Distinct from `queries/dnssec.py` and `queries/policies.py`:
DnsFilteringProfile is its own GraphQL type (multiple profiles per tenant,
each assigned to a set of Groups) -- not the single implicit profile the
legacy `dnssec` commands assume, and not a Resource/Security Policy.
"""

from __future__ import annotations

from tgcli.queries.nested import connection, continuation

LIST_DNS_PROFILES = """
query listDnsProfiles {
  dnsFilteringProfiles {
    id
    name
    priority
  }
}
"""

# The API returns at most 50 items per page, so `dns-profile show` follows each nested list to its end.
_NESTED = {"groups": "node { id name }"}

SHOW_DNS_PROFILE = f"""
query getDnsProfile($itemID: ID!) {{
  dnsFilteringProfile(id: $itemID) {{
    id
    name
    priority
    fallbackMethod
    allowedDomains
    deniedDomains
    {connection("groups", _NESTED["groups"])}
  }}
}}
"""

DNS_PROFILE_CONTINUATIONS = {field: continuation("dnsFilteringProfile", field, edge) for field, edge in _NESTED.items()}

FIND_DNS_PROFILE = """
query findDnsProfile($itemID: ID!) {
  dnsFilteringProfile(id: $itemID) {
    id
  }
}
"""

CREATE_DNS_PROFILE = """
mutation createDnsProfile($name: String!) {
  dnsFilteringProfileCreate(name: $name) {
    ok
    error
    entity {
      id
      name
      priority
    }
  }
}
"""

DELETE_DNS_PROFILE = """
mutation deleteDnsProfile($id: ID!) {
  dnsFilteringProfileDelete(id: $id) {
    ok
    error
  }
}
"""
