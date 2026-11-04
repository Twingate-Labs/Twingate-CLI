"""A small stateful fake of the parts of the Twingate API that `tgcli import` uses.

It serves tiny pages (2 items) so pagination is always exercised, only returns the fields a query actually selects (so a
query that forgets one is noticed), refuses variables a mutation does not declare, and applies writes to its own state,
so running an import twice shows whether the second run really finds nothing to do.
"""

from __future__ import annotations

import re
from typing import Any

from tgcli.client.exceptions import TwingateAPIError

PAGE = 2
FIELDS = {"networks": ("id", "name"), "service_accounts": ("id", "name"), "groups": ("id", "name", "type"), "users": ("id", "email"), "policies": ("id", "name", "policyType")}
ROOTS = {"remoteNetworks": "networks", "groups": "groups", "users": "users", "securityPolicies": "policies", "resources": "resources", "devices": "devices", "serviceAccounts": "service_accounts"}


ALL_PORTS = {"policy": "ALLOW_ALL", "ports": []}
TYPENAME = {"NETWORK": "NetworkResource", "SSH": "SSHResource", "WEB_APP": "WebAppResource", "KUBERNETES": "KubernetesResource"}
TYPED_MUTATION = re.compile(r"import(Ssh|WebApp|Kubernetes)Resource(Create|Update)$")
TYPED_KIND = {"Ssh": "SSH", "WebApp": "WEB_APP", "Kubernetes": "KUBERNETES"}
GATEWAY_FIELDS = ("gateway", "upstream", "downstream", "clusterRef", "requestHeaderRewrites")


def resource_detail(obj: dict) -> dict:
    """The settings of a fake resource in the shape the API returns them, with the API's defaults for what a test left out."""
    detail = {
        "alias": obj.get("alias"), "isVisible": obj.get("isVisible", True), "isBrowserShortcutEnabled": obj.get("isBrowserShortcutEnabled", True),
        "approvalMode": obj.get("approvalMode", "MANUAL"), "securityPolicy": obj.get("securityPolicy"),
        "accessPolicy": obj.get("accessPolicy", {"mode": "MANUAL", "durationSeconds": None}),
        "protocols": obj.get("protocols", {"allowIcmp": True, "tcp": ALL_PORTS, "udp": ALL_PORTS}),
        "tags": obj.get("tags", []), "routingMode": obj.get("routingMode", "THROUGH_TWINGATE"),
    }
    detail.update({key: obj[key] for key in GATEWAY_FIELDS if key in obj})  # only an SSH, web app or Kubernetes resource has these
    return detail


def page(items: list, cursor: Any) -> tuple:
    start = 0 if cursor is None else int(cursor[1:])
    more = start + PAGE < len(items)
    return items[start : start + PAGE], {"hasNextPage": more, "endCursor": f"c{start + PAGE}" if more else None}


class FakeApi:
    def __init__(self, networks=(), groups=(), users=(), policies=(), resources=(), devices=(), service_accounts=(), gateways=()):
        self.gateways = [dict(g) for g in gateways]  # {"id", "address", "remoteNetwork": {"id", "name"}, "x509CA", "sshCA"}
        self.cas: list = []  # certificate authorities: {"id", "name", "fingerprint", "type"}
        self.ca_fingerprint = None  # a callable(type, content) -> the fingerprint the API reports for a CA it is given; None = what ca_material.api_fingerprint says
        self.unreadable: dict = {}  # a query's root field -> the error the API gives when it is read (a tenant without that feature)
        self.connectors: list = []  # {"id", "name", "hasStatusNotificationsEnabled", "remoteNetwork": {"id", "name"}}
        self.dns_profiles: list = []  # as in a backup, but "groups" is a list of group IDs
        self.devices = [{"activeState": "ACTIVE", "user": {"email": "ann@x.com"}, **d} for d in devices]
        self.ignore_trust = False  # the API accepts a trust change but reports the device unchanged
        self.networks = [dict(n) for n in networks]
        self.groups = [{**g, "members": set(g.get("members", ()))} for g in groups]
        self.users = [dict(u) for u in users]
        self.service_accounts = [dict(a) for a in service_accounts]
        self.policies = [dict(p) for p in policies]
        self.resources = [{**r, "access": dict(r.get("access", {}))} for r in resources]
        self.requests: list = []
        self.fail: dict = {}  # mutation name -> message, or a callable(variables) returning a message or None
        self.raise_on: dict = {}  # mutation or query name -> exception to raise
        self.counter = 0

    @property
    def writes(self) -> list:
        return [(self._name(q), v) for q, v in self.requests if q.lstrip().startswith("mutation")]

    @property
    def lookups(self) -> list:
        return [(q, v) for q, v in self.requests if "filter: {" in q]

    @staticmethod
    def _name(query: str) -> str:
        return re.search(r"(?:query|mutation) (\w+)", query).group(1) if re.search(r"(?:query|mutation) (\w+)", query) else "query"

    def _new_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-{self.counter}"

    def execute(self, query: str, variables: dict | None = None) -> dict:
        variables = variables or {}
        self.requests.append((query, variables))
        name = self._name(query)
        if name in self.raise_on:
            raise self.raise_on[name]
        if query.lstrip().startswith("mutation"):
            return self._mutate(name, query, variables)
        return self._read(query, variables)

    # ------------------------------------------------------------------ reads

    def _read(self, query: str, variables: dict) -> dict:
        cursor = variables.get("cursor")
        lookup = re.search(r"(\w+)\(after: \$cursor, filter: \{(\w+): \{in: \$names\}\}\)", query)
        if lookup:
            root, field = lookup.groups()
            kind = ROOTS[root]
            wanted = set(variables["names"])
            key = {"email": "email", "serialNumber": "serialNumber"}.get(field, "name")
            hits = [o for o in getattr(self, kind) if o[key] in wanted]
            nodes = []
            for obj in hits:
                if kind == "resources":
                    assert "address { value }" in query, "resources are matched by address too"
                    node = {"id": obj["id"], "name": obj["name"], "remoteNetwork": {"name": obj["network"]},
                            "address": {"value": obj.get("address", f"{obj['name'].lower()}.internal")}}
                    if "__typename" in query:
                        node["__typename"] = TYPENAME[obj.get("type", "NETWORK")]
                    if "alias isVisible" in query:
                        node.update(resource_detail(obj))
                elif kind == "devices":
                    node = {k: obj[k] for k in ("id", "serialNumber", "isTrusted", "activeState", "user") if k in query.split("node {", 1)[1] or k == "id"}
                else:
                    node = {k: obj[k] for k in FIELDS[kind] if k in query.split("node {", 1)[1] and k in obj}
                    if kind == "groups" and "securityPolicy { id }" in query:
                        node["securityPolicy"] = {"id": obj["securityPolicyId"]} if obj.get("securityPolicyId") else None
                nodes.append(node)
            chunk, info = page(nodes, cursor)
            return {"data": {root: {"pageInfo": info, "edges": [{"node": n} for n in chunk]}}}
        for root in self.unreadable:
            if root in query:
                raise self.unreadable[root]
        if "certificateAuthorities(after: $cursor)" in query:
            chunk, info = page([dict(c) for c in self.cas], cursor)
            typename = {"x509": "X509CertificateAuthority", "ssh": "SSHCertificateAuthority"}
            nodes = [{"__typename": typename[c["type"]], "id": c["id"], "name": c["name"], "fingerprint": c["fingerprint"]} for c in chunk]
            return {"data": {"certificateAuthorities": {"pageInfo": info, "edges": [{"node": n} for n in nodes]}}}
        if "dnsFilteringProfiles {" in query:
            return {"data": {"dnsFilteringProfiles": [{"id": p["id"], "name": p["name"]} for p in self.dns_profiles]}}
        if "approverGroups(after: $cursor)" in query:
            res = next((r for r in self.resources if r["id"] == variables["id"]), None)
            chunk, info = page(sorted(res.get("approvers") or ()), cursor)
            return {"data": {"resource": {"approverGroups": {"pageInfo": info, "edges": [{"node": {"id": g, "name": g}} for g in chunk]}}}}
        if "gateways(after: $cursor)" in query:
            chunk, info = page([dict(g) for g in self.gateways], cursor)
            return {"data": {"gateways": {"pageInfo": info, "edges": [{"node": n} for n in chunk]}}}
        if "group(id: $id)" in query:
            group = next((g for g in self.groups if g["id"] == variables["id"]), None)
            if group is None:
                return {"data": {"group": None}}
            chunk, info = page(sorted(group["members"]), cursor)
            if "email" in query:
                nodes = [{"id": u, "email": next(x["email"] for x in self.users if x["id"] == u)} for u in chunk]
            else:
                nodes = [{"id": u} for u in chunk]
            return {"data": {"group": {"users": {"pageInfo": info, "edges": [{"node": n} for n in nodes]}}}}
        if "resource(id: $id)" in query:
            res = next((r for r in self.resources if r["id"] == variables["id"]), None)
            if res is None:
                return {"data": {"resource": None}}
            chunk, info = page(sorted(res["access"]), cursor)
            if "approvalMode expiresAt" in query:
                edges = []
                for principal in chunk:
                    entry = res["access"][principal]
                    who = next(x for x in self.groups + self.service_accounts if x["id"] == principal)
                    edges.append({
                        "node": {"id": principal, "name": who["name"]},
                        "securityPolicy": {"id": entry["securityPolicyId"]} if entry.get("securityPolicyId") else None,
                        "accessPolicy": entry.get("accessPolicy"), "approvalMode": entry.get("approvalMode", "MANUAL"),
                        "expiresAt": entry.get("expiresAt"),
                    })
            else:
                edges = [{"node": {"id": g}} for g in chunk]
            return {"data": {"resource": {"access": {"pageInfo": info, "edges": edges}}}}
        raise AssertionError(f"unrecognised query: {query[:100]}")

    # ------------------------------------------------------------------ writes

    def _mutate(self, name: str, query: str, variables: dict) -> dict:
        declared = set(re.findall(r"\$(\w+):", query.split(")", 1)[0]))
        assert set(variables) <= declared, f"{name} sent undeclared variables {set(variables) - declared}"
        if name.startswith("restore") or name in ("createX509CA", "createSSHCA"):
            return self._mutate_restore(name, query, variables)
        typed = TYPED_MUTATION.match(name)
        if typed:
            return self._mutate_typed(name, typed.group(1), typed.group(2) == "Create", query, variables)
        field = {"importNetwork": "remoteNetworkCreate", "importGroup": "groupCreate", "importGroupUsers": "groupUpdate",
                 "importResource": "resourceCreate", "importAccess": "resourceAccessAdd", "importDeviceTrust": "deviceUpdate",
                 "importResourceUpdate": "resourceUpdate", "importAccessRemove": "resourceAccessRemove", "importGroupSync": "groupUpdate",
                 "importNetworkUpdate": "remoteNetworkUpdate"}[name]
        problem = self.fail.get(name)
        if callable(problem):
            problem = problem(variables)
        if problem:
            return {"data": {field: {"ok": False, "error": problem, "entity": None}}}
        entity = getattr(self, "_do_" + name)(variables)
        return {"data": {field: {"ok": True, "error": None, "entity": entity}}}

    def _do_importNetwork(self, v: dict) -> dict:
        assert not any(n["name"] == v["name"] for n in self.networks), "duplicate network"
        net = {"id": self._new_id("net"), "name": v["name"], "location": v.get("location"), "networkType": v.get("networkType"), "isActive": v.get("isActive")}
        self.networks.append(net)
        return {"id": net["id"], "name": net["name"]}

    def _do_importGroup(self, v: dict) -> dict:
        group = {"id": self._new_id("grp"), "name": v["name"], "type": "MANUAL", "members": set(), "securityPolicyId": v.get("securityPolicyId")}
        self.groups.append(group)
        return {"id": group["id"], "name": group["name"]}

    def _do_importGroupUsers(self, v: dict) -> dict:
        assert len(v["userIds"]) <= 200
        next(g for g in self.groups if g["id"] == v["id"])["members"].update(v["userIds"])
        return {"id": v["id"]}

    def _do_importResource(self, v: dict) -> dict:
        network = next(n for n in self.networks if n["id"] == v["remoteNetworkId"])
        res = {"id": self._new_id("res"), "name": v["name"], "network": network["name"], "address": v["address"], "access": {}, "variables": v,
               "approvers": set(v.get("approverGroupIds") or [])}
        for key in ("alias", "isVisible", "isBrowserShortcutEnabled", "approvalMode", "accessPolicy", "protocols", "tags", "routingMode"):
            if key in v:
                res[key] = v[key]
        if v.get("securityPolicyId"):
            res["securityPolicy"] = {"id": v["securityPolicyId"]}
        self.resources.append(res)
        return {"id": res["id"], "name": res["name"]}

    def _do_importAccess(self, v: dict) -> dict:
        res = next(r for r in self.resources if r["id"] == v["id"])
        for entry in v["access"]:
            principal = entry["principalId"]
            if any(a["id"] == principal for a in self.service_accounts):
                # what the real API does: a service account's grant takes no settings at all, not even a default one
                assert set(entry) == {"principalId"}, f"a service account's grant carries settings: {sorted(set(entry) - {'principalId'})}"
            else:
                assert next((g for g in self.groups if g["id"] == principal), None), "access for a group that does not exist"
            # an existing grant keeps whatever the call does not mention (the real API does), a new one starts from the call
            res["access"][principal] = {**res["access"].get(principal, {}), **entry}
        return {"id": v["id"]}

    def _do_importResourceUpdate(self, v: dict) -> dict:
        res = next(r for r in self.resources if r["id"] == v["id"])
        for key, value in v.items():
            if key == "id":
                continue
            if key == "securityPolicyId":
                res["securityPolicy"] = {"id": value} if value else None
            elif key == "remoteNetworkId":
                res["network"] = next(n["name"] for n in self.networks if n["id"] == value)
            elif key in ("addedApproverGroupIds", "removedApproverGroupIds"):
                continue
            else:
                res[key] = value
        self._approvers(res, v)
        if "accessPolicy" in v and "approvalMode" not in v:
            res["approvalMode"] = "MANUAL"  # what the real API does: changing the access policy alone resets the approval mode
        res.setdefault("updates", []).append(v)
        return {"id": res["id"]}

    @staticmethod
    def _approvers(res: dict, v: dict) -> None:
        res["approvers"] = (set(res.get("approvers") or ()) | set(v.get("addedApproverGroupIds") or ())) - set(v.get("removedApproverGroupIds") or ())

    def _do_importAccessRemove(self, v: dict) -> dict:
        res = next(r for r in self.resources if r["id"] == v["id"])
        for principal in v["principalIds"]:
            assert principal in res["access"], "removing access that is not there"
            del res["access"][principal]
        return {"id": res["id"]}

    def _do_importGroupSync(self, v: dict) -> dict:
        group = next(g for g in self.groups if g["id"] == v["id"])
        assert len(v.get("removedUserIds") or []) <= 200
        if "securityPolicyId" in v:
            group["securityPolicyId"] = v["securityPolicyId"]
        for key in ("name", "isActive"):
            if key in v:
                group[key] = v[key]
        group["members"].difference_update(v.get("removedUserIds") or [])
        return {"id": group["id"]}

    def _do_importNetworkUpdate(self, v: dict) -> dict:
        network = next(n for n in self.networks if n["id"] == v["id"])
        if "name" in v:  # resources stay in their network when it is renamed
            for res in self.resources:
                if res["network"] == network["name"]:
                    res["network"] = v["name"]
        network.update({k: val for k, val in v.items() if k != "id"})
        return {"id": network["id"]}

    def _do_importDeviceTrust(self, v: dict) -> dict:
        device = next(d for d in self.devices if d["id"] == v["id"])
        if not self.ignore_trust:
            device["isTrusted"] = v["isTrusted"]
        return {"id": device["id"], "isTrusted": device["isTrusted"]}

    # ------------------------------------------------------------------ SSH, web app and Kubernetes resources

    def _mutate_typed(self, name: str, flavour: str, create: bool, query: str, variables: dict) -> dict:
        field = re.search(r"\) \{ (\w+)\(", query).group(1)
        problem = self.fail.get(name)
        if callable(problem):
            problem = problem(variables)
        if problem:
            return {"data": {field: {"ok": False, "error": problem, "entity": None}}}
        kind = TYPED_KIND[flavour]
        if create:
            network = next(n for n in self.networks if n["id"] == variables["remoteNetworkId"])
            if kind != "KUBERNETES":
                assert variables.get("gatewayId"), "the API requires a Gateway for this type"
            if kind == "WEB_APP":
                assert variables.get("upstream", {}).get("port") and variables.get("downstream", {}).get("port"), "a web app needs both ports"
            res = {"id": self._new_id("res"), "name": variables["name"], "network": network["name"], "address": variables["address"], "access": {}, "type": kind}
        else:
            res = next(r for r in self.resources if r["id"] == variables["id"])
            assert res.get("type", "NETWORK") == kind, "the API cannot update a resource with another type's mutation"
        for key, value in variables.items():
            if key == "id":
                continue
            if key == "gatewayId":
                gateway = next((g for g in self.gateways if g["id"] == value), None)
                assert gateway, "a Gateway that does not exist"
                res["gateway"] = {"id": gateway["id"], "address": gateway["address"]}
            elif key == "securityPolicyId":
                res["securityPolicy"] = {"id": value} if value else None
            elif key == "remoteNetworkId":
                res["network"] = next(n["name"] for n in self.networks if n["id"] == value)
            elif key in ("approverGroupIds", "addedApproverGroupIds", "removedApproverGroupIds"):
                continue
            else:
                res[key] = value
        res["approvers"] = set(variables.get("approverGroupIds") or ()) if create else set(res.get("approvers") or ())
        self._approvers(res, variables)
        if "accessPolicy" in variables and "approvalMode" not in variables:
            res["approvalMode"] = "MANUAL"
        res.setdefault("updates", []).append(variables)
        res["variables"] = variables
        if create:
            self.resources.append(res)
        return {"data": {field: {"ok": True, "error": None, "entity": {"id": res["id"], "name": res["name"]}}}}

    # ------------------------------------------------------------------ what only `tgcli restore` writes

    def _mutate_restore(self, name: str, query: str, variables: dict) -> dict:
        field = re.search(r"\) \{\s*(\w+)\(", query).group(1)
        problem = self.fail.get(name)
        if callable(problem):
            problem = problem(variables)
        if problem:
            return {"data": {field: {"ok": False, "error": problem, "entity": None}}}
        entity = getattr(self, "_do_" + name)(variables)
        return {"data": {field: {"ok": True, "error": None, "entity": entity}}}

    def _make_ca(self, kind: str, name: str, content: str) -> dict:
        from tests.importer.ca_material import api_fingerprint

        fingerprint = (self.ca_fingerprint or api_fingerprint)(kind, content)
        ca = {"id": self._new_id("ca"), "name": name, "fingerprint": fingerprint, "type": kind}
        self.cas.append(ca)
        return {"id": ca["id"], "name": name, "fingerprint": fingerprint}

    def _do_createX509CA(self, v: dict) -> dict:
        return self._make_ca("x509", v["name"], v["certificate"])

    def _do_createSSHCA(self, v: dict) -> dict:
        return self._make_ca("ssh", v["name"], v["publicKey"])

    def _do_restoreServiceAccountCreate(self, v: dict) -> dict:
        account = {"id": self._new_id("sa"), "name": v["name"]}
        self.service_accounts.append(account)
        return dict(account)

    def _do_restoreServiceAccountUpdate(self, v: dict) -> dict:
        account = next(a for a in self.service_accounts if a["id"] == v["id"])
        account.update({k: val for k, val in v.items() if k != "id"})
        return dict(account)

    def _ca(self, ca_id: str) -> dict:
        ca = next((c for c in self.cas if c["id"] == ca_id), None)
        assert ca, "a certificate authority that does not exist"
        return {"id": ca["id"], "name": ca["name"], "fingerprint": ca["fingerprint"]}

    def _gateway_fields(self, gateway: dict, v: dict) -> None:
        for key, value in v.items():
            if key == "id":
                continue
            if key == "remoteNetworkId":
                network = next(n for n in self.networks if n["id"] == value)
                gateway["remoteNetwork"] = {"id": network["id"], "name": network["name"]}
            elif key == "x509CAId":
                gateway["x509CA"] = self._ca(value)
            elif key == "sshCAId":
                gateway["sshCA"] = self._ca(value)
            else:
                gateway[key] = value

    def _do_restoreGatewayCreate(self, v: dict) -> dict:
        assert not any(g["address"] == v["address"] and g["remoteNetwork"]["id"] == v["remoteNetworkId"] for g in self.gateways), "duplicate Gateway"
        gateway = {"id": self._new_id("gw"), "address": v["address"], "sshCA": None}
        self._gateway_fields(gateway, v)
        self.gateways.append(gateway)
        return {"id": gateway["id"], "address": gateway["address"]}

    def _do_restoreGatewayUpdate(self, v: dict) -> dict:
        gateway = next(g for g in self.gateways if g["id"] == v["id"])
        self._gateway_fields(gateway, v)
        return {"id": gateway["id"], "address": gateway["address"]}

    def _do_restoreUserRole(self, v: dict) -> dict:
        user = next(u for u in self.users if u["id"] == v["id"])
        user["role"] = v["role"]
        return {"id": user["id"], "email": user["email"], "role": user["role"]}

    def _do_restoreConnectorCreate(self, v: dict) -> dict:
        network = next(n for n in self.networks if n["id"] == v["remoteNetworkId"])
        connector = {"id": self._new_id("con"), "name": v["name"], "hasStatusNotificationsEnabled": v.get("hasStatusNotificationsEnabled", True),
                     "remoteNetwork": {"id": network["id"], "name": network["name"]}}
        self.connectors.append(connector)
        return {"id": connector["id"], "name": connector["name"]}

    def _do_restoreConnectorUpdate(self, v: dict) -> dict:
        connector = next(c for c in self.connectors if c["id"] == v["id"])
        connector.update({k: val for k, val in v.items() if k != "id"})
        return {"id": connector["id"], "name": connector["name"]}

    def _do_restoreDeviceTrust(self, v: dict) -> dict:
        device = next(d for d in self.devices if d["id"] == v["id"])
        assert not device.get("verified") or v["isTrusted"], "Serial number verified Devices cannot be unverified via API"
        device["isTrusted"] = v["isTrusted"]
        return {"id": device["id"], "isTrusted": device["isTrusted"]}

    def _device_move(self, v: dict, before: str, after: str) -> dict:
        device = next(d for d in self.devices if d["id"] == v["id"])
        assert device["activeState"] == before, f"the API only does this to a {before} device, this one is {device['activeState']}"
        device["activeState"] = after
        return {"id": device["id"], "activeState": after}

    def _do_restoreDeviceBlock(self, v: dict) -> dict:
        return self._device_move(v, "ACTIVE", "BLOCKED")

    def _do_restoreDeviceUnblock(self, v: dict) -> dict:
        return self._device_move(v, "BLOCKED", "ACTIVE")

    def _do_restoreDeviceArchive(self, v: dict) -> dict:
        return self._device_move(v, "ACTIVE", "ARCHIVED")

    def _do_restoreDeviceUnarchive(self, v: dict) -> dict:
        return self._device_move(v, "ARCHIVED", "ACTIVE")

    def _do_restoreDnsProfileCreate(self, v: dict) -> dict:
        profile = {
            "id": self._new_id("dns"), "name": v["name"], "priority": 1.0, "fallbackMethod": "AUTO", "allowedDomains": [], "deniedDomains": [],
            "contentCategoryConfig": {"blockGambling": False}, "securityCategoryConfig": {"blockCryptojacking": True},
            "privacyCategoryConfig": {"blockAdsAndTrackers": False}, "groups": [],
        }
        self.dns_profiles.append(profile)
        return {"id": profile["id"], "name": profile["name"]}

    def _do_restoreDnsProfileUpdate(self, v: dict) -> dict:
        profile = next(p for p in self.dns_profiles if p["id"] == v["id"])
        for key, value in v.items():
            if key != "id":
                profile[key] = value
        return {"id": profile["id"], "name": profile["name"]}
