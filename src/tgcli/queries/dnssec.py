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

CREATE_DNS_PROFILE = """
mutation createDnsProfile($name: String!) {
  dnsFilteringProfileCreate(name: $name) {
    ok
    error
    entity {
      id
      name
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

UPDATE_DNS_PROFILE_FULL = """
mutation updateDnsProfileFull(
  $id: ID!
  $name: String
  $priority: Float
  $fallbackMethod: DnsFilteringFallbackMethod
  $groups: [ID!]
  $allowedDomains: [String!]
  $deniedDomains: [String!]
  $contentCategoryConfig: DnsFilteringContentCategoryConfigInput
  $securityCategoryConfig: DnsFilteringSecurityCategoryConfigInput
  $privacyCategoryConfig: DnsFilteringPrivacyCategoryConfigInput
) {
  dnsFilteringProfileUpdate(
    id: $id
    name: $name
    priority: $priority
    fallbackMethod: $fallbackMethod
    groups: $groups
    allowedDomains: $allowedDomains
    deniedDomains: $deniedDomains
    contentCategoryConfig: $contentCategoryConfig
    securityCategoryConfig: $securityCategoryConfig
    privacyCategoryConfig: $privacyCategoryConfig
  ) {
    ok
    error
    entity {
      id
      name
      allowedDomains
      deniedDomains
    }
  }
}
"""
