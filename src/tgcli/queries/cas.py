"""GraphQL queries and mutations for certificate authorities."""

from __future__ import annotations

LIST_CAS = """
query listCertificateAuthorities($cursor: String!) {
  certificateAuthorities(after: $cursor, first: null) {
    totalCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        ... on SSHCertificateAuthority {
          id
          name
          fingerprint
        }
        ... on X509CertificateAuthority {
          id
          name
        }
      }
    }
  }
}
"""

SHOW_CA = """
query getCertificateAuthority($itemID: ID!) {
  certificateAuthority(id: $itemID) {
    ... on SSHCertificateAuthority {
      id
      name
      fingerprint
    }
    ... on X509CertificateAuthority {
      id
      name
    }
  }
}
"""

CREATE_SSH_CA = """
mutation createSshCA($name: String!, $publicKey: String!) {
  sshCertificateAuthorityCreate(name: $name, publicKey: $publicKey) {
    ok
    error
    entity {
      id
      name
      fingerprint
    }
  }
}
"""

DELETE_SSH_CA = """
mutation deleteSshCA($id: ID!) {
  sshCertificateAuthorityDelete(id: $id) {
    ok
    error
  }
}
"""

CREATE_X509_CA = """
mutation createX509CA($name: String!, $certificate: String!) {
  x509CertificateAuthorityCreate(name: $name, certificate: $certificate) {
    ok
    error
    entity {
      id
      name
    }
  }
}
"""

DELETE_X509_CA = """
mutation deleteX509CA($id: ID!) {
  x509CertificateAuthorityDelete(id: $id) {
    ok
    error
  }
}
"""

HEALTH_CAS = """
{ certificateAuthorities(first: null, after: "0") { totalCount edges { node { ... on SSHCertificateAuthority { id } ... on X509CertificateAuthority { id } } } } }
"""
