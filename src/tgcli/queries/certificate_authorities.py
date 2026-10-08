"""GraphQL queries and mutations for certificate authorities (X.509 and SSH)."""

from __future__ import annotations

_CA_FIELDS = """
      __typename
      ... on X509CertificateAuthority {
        id
        name
        fingerprint
      }
      ... on SSHCertificateAuthority {
        id
        name
        fingerprint
      }
"""

LIST_CAS = """
query listCertificateAuthorities($cursor: String!) {
  certificateAuthorities(after: $cursor, first: null) {
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {""" + _CA_FIELDS + """      }
    }
  }
}
"""

SHOW_CA = """
query getCertificateAuthority($itemID: ID!) {
  certificateAuthority(id: $itemID) {""" + _CA_FIELDS + """  }
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
      fingerprint
    }
  }
}
"""

CREATE_SSH_CA = """
mutation createSSHCA($name: String!, $publicKey: String!) {
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

DELETE_X509_CA = """
mutation deleteX509CA($id: ID!) {
  x509CertificateAuthorityDelete(id: $id) {
    ok
    error
  }
}
"""

DELETE_SSH_CA = """
mutation deleteSSHCA($id: ID!) {
  sshCertificateAuthorityDelete(id: $id) {
    ok
    error
  }
}
"""
