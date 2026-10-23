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
FIELDS = {"networks": ("id", "name"), "groups": ("id", "name", "type"), "users": ("id", "email"), "policies": ("id", "name", "policyType")}
ROOTS = {"remoteNetworks": "networks", "groups": "groups", "users": "users", "securityPolicies": "policies", "resources": "resources", "devices": "devices"}


def page(items: list, cursor: Any) -> tuple:
    start = 0 if cursor is None else int(cursor[1:])
    more = start + PAGE < len(items)
    return items[start : start + PAGE], {"hasNextPage": more, "endCursor": f"c{start + PAGE}" if more else None}


class FakeApi:
    def __init__(self, networks=(), groups=(), users=(), policies=(), resources=(), devices=()):
        self.devices = [{"activeState": "ACTIVE", "user": {"email": "ann@x.com"}, **d} for d in devices]
        self.ignore_trust = False  # the API accepts a trust change but reports the device unchanged
        self.networks = [dict(n) for n in networks]
        self.groups = [{**g, "members": set(g.get("members", ()))} for g in groups]
        self.users = [dict(u) for u in users]
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
                elif kind == "devices":
                    node = {k: obj[k] for k in ("id", "serialNumber", "isTrusted", "activeState", "user") if k in query.split("node {", 1)[1] or k == "id"}
                else:
                    node = {k: obj[k] for k in FIELDS[kind] if k in query.split("node {", 1)[1] and k in obj}
                nodes.append(node)
            chunk, info = page(nodes, cursor)
            return {"data": {root: {"pageInfo": info, "edges": [{"node": n} for n in chunk]}}}
        if "group(id: $id)" in query:
            group = next((g for g in self.groups if g["id"] == variables["id"]), None)
            if group is None:
                return {"data": {"group": None}}
            chunk, info = page(sorted(group["members"]), cursor)
            return {"data": {"group": {"users": {"pageInfo": info, "edges": [{"node": {"id": u}} for u in chunk]}}}}
        if "resource(id: $id)" in query:
            res = next((r for r in self.resources if r["id"] == variables["id"]), None)
            if res is None:
                return {"data": {"resource": None}}
            chunk, info = page(sorted(res["access"]), cursor)
            return {"data": {"resource": {"access": {"pageInfo": info, "edges": [{"node": {"id": g}} for g in chunk]}}}}
        raise AssertionError(f"unrecognised query: {query[:100]}")

    # ------------------------------------------------------------------ writes

    def _mutate(self, name: str, query: str, variables: dict) -> dict:
        declared = set(re.findall(r"\$(\w+):", query.split(")", 1)[0]))
        assert set(variables) <= declared, f"{name} sent undeclared variables {set(variables) - declared}"
        field = {"importNetwork": "remoteNetworkCreate", "importGroup": "groupCreate", "importGroupUsers": "groupUpdate",
                 "importResource": "resourceCreate", "importAccess": "resourceAccessAdd", "importDeviceTrust": "deviceUpdate"}[name]
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
        res = {"id": self._new_id("res"), "name": v["name"], "network": network["name"], "address": v["address"], "access": {}, "variables": v}
        self.resources.append(res)
        return {"id": res["id"], "name": res["name"]}

    def _do_importAccess(self, v: dict) -> dict:
        res = next(r for r in self.resources if r["id"] == v["id"])
        for entry in v["access"]:
            assert next((g for g in self.groups if g["id"] == entry["principalId"]), None), "access for a group that does not exist"
            res["access"][entry["principalId"]] = entry
        return {"id": v["id"]}

    def _do_importDeviceTrust(self, v: dict) -> dict:
        device = next(d for d in self.devices if d["id"] == v["id"])
        if not self.ignore_trust:
            device["isTrusted"] = v["isTrusted"]
        return {"id": device["id"], "isTrusted": device["isTrusted"]}
