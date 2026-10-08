"""GraphQL mutations for SSH, web app and Kubernetes resources."""

from __future__ import annotations

_COMMON_CREATE = [
    ("name", "String!"), ("address", "String!"), ("remoteNetworkId", "ID!"), ("alias", "String"),
    ("securityPolicyId", "ID"), ("groupIds", "[ID]"), ("isVisible", "Boolean"),
]
_COMMON_UPDATE = [
    ("id", "ID!"), ("name", "String"), ("address", "String"), ("alias", "String"), ("remoteNetworkId", "ID"),
    ("gatewayId", "ID"), ("securityPolicyId", "ID"), ("isVisible", "Boolean"), ("isActive", "Boolean"),
    ("addedGroupIds", "[ID]"), ("removedGroupIds", "[ID]"),
]
_ENTITY = """
      id
      name
      isActive
      isVisible
      address {
        value
      }
      remoteNetwork {
        id
        name
      }
      gateway {
        id
      }
"""


def _mutation(label: str, field: str, variables: list[tuple[str, str]], entity_extra: str) -> str:
    declared = ", ".join(f"${name}: {gql_type}" for name, gql_type in variables)
    passed = ", ".join(f"{name}: ${name}" for name, _ in variables)
    return f"""
mutation {label}({declared}) {{
  {field}({passed}) {{
    ok
    error
    entity {{{_ENTITY}{entity_extra}    }}
  }}
}}
"""


_PORT = "      {0} {{\n        port\n      }}\n"
_PORT_TLS = "      {0} {{\n        port\n        tlsMode\n      }}\n"
_PORTS = _PORT.format("upstream") + _PORT.format("downstream")
_PORTS_TLS = _PORT_TLS.format("upstream") + _PORT_TLS.format("downstream")

_SSH = [("gatewayId", "ID!"), ("upstream", "SSHUpstreamInput"), ("downstream", "SSHDownstreamInput")]
_WEBAPP = [
    ("gatewayId", "ID!"), ("upstream", "WebAppUpstreamInput!"), ("downstream", "WebAppDownstreamInput!"),
    ("requestHeaderRewrites", "[KeyValueInputObject!]"),
]
_K8S = [
    ("gatewayId", "ID"), ("clusterRef", "String"), ("upstream", "KubernetesUpstreamInput"),
    ("downstream", "KubernetesDownstreamInput"),
]
_UPDATE_SSH = [("upstream", "SSHUpstreamInput"), ("downstream", "SSHDownstreamInput")]
_UPDATE_WEBAPP = [
    ("upstream", "WebAppUpstreamInput"), ("downstream", "WebAppDownstreamInput"),
    ("requestHeaderRewrites", "[KeyValueInputObject!]"),
]
_UPDATE_K8S = [
    ("clusterRef", "String"), ("upstream", "KubernetesUpstreamInput"), ("downstream", "KubernetesDownstreamInput"),
]

CREATE_SSH_RESOURCE = _mutation("createSSHResource", "sshResourceCreate", _COMMON_CREATE + _SSH, _PORTS)
UPDATE_SSH_RESOURCE = _mutation("updateSSHResource", "sshResourceUpdate", _COMMON_UPDATE + _UPDATE_SSH, _PORTS)
CREATE_WEBAPP_RESOURCE = _mutation("createWebAppResource", "webAppResourceCreate", _COMMON_CREATE + _WEBAPP, _PORTS_TLS)
UPDATE_WEBAPP_RESOURCE = _mutation("updateWebAppResource", "webAppResourceUpdate", _COMMON_UPDATE + _UPDATE_WEBAPP, _PORTS_TLS)
CREATE_K8S_RESOURCE = _mutation("createK8sResource", "kubernetesResourceCreate", _COMMON_CREATE + _K8S, "      clusterRef\n" + _PORTS)
UPDATE_K8S_RESOURCE = _mutation("updateK8sResource", "kubernetesResourceUpdate", _COMMON_UPDATE + _UPDATE_K8S, "      clusterRef\n" + _PORTS)
