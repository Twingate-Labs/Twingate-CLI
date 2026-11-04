"""What an import cannot carry from a backup into another tenant, said plainly instead of left out silently.

Only what the backup actually holds is mentioned: an import of a few CSV files has nothing to say here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tgcli.importer.cafiles import CaFiles
from tgcli.importer.load import Specs
from tgcli.importer.plan import SKIP, Row

USERS, CONNECTORS, POLICIES, DEVICES = "users.json", "connectors.json", "security-policies.json", "devices.json"


@dataclass
class Notice:
    what: str  # "users", "service account keys"...
    detail: str  # how many, and why they cannot be carried over, and what to do instead
    source: str = ""  # the backup file it concerns


def _many(count: Optional[int], word: str, plural: str = "") -> str:
    if count is None:
        return f"the {plural or word + 's'}"
    return f"{count} {word if count == 1 else plural or word + 's'}"


def not_carried_over(specs: Specs, rows: list, ca_files: Optional[CaFiles] = None) -> list:
    """The notices for this import, in a fixed order."""
    out: list = []
    counts = specs.counts
    if USERS in counts:
        out.append(Notice(
            "users", f"Not created ({_many(counts[USERS], 'user')} in the backup): users come from the identity provider. A group's members "
            "are matched by email to users who already exist in this tenant, and any that are not found are listed as warnings on the group.", USERS))
    if CONNECTORS in counts:
        out.append(Notice(
            "connectors", f"Not created ({_many(counts[CONNECTORS], 'Connector')} in the backup): a Connector needs its own tokens and a deployment. "
            "Create each with `tgcli connector create` and deploy it.", CONNECTORS))
    if POLICIES in counts:
        out.append(Notice(
            "security policies", f"Not created, nor are their rules ({_many(counts[POLICIES], 'Security Policy', 'Security Policies')} in the backup): the API "
            "cannot create them. A group, resource or grant that names a Policy needs one with that name in this tenant (otherwise its row is blocked, "
            "or the grant is left out and says so).", POLICIES))
    if DEVICES in counts:
        out.append(Notice(
            "device registrations", f"Not carried over ({_many(counts[DEVICES], 'device')} in the backup): a device registers itself from the user's own "
            "Twingate Client. A devices.csv sets trust on devices that have registered in this tenant.", DEVICES))
    keys = sum(s.keys for s in specs.service_accounts)
    if keys:
        out.append(Notice(
            "service account keys", f"Not carried over ({_many(keys, 'key')} in the backup): the API never returns a key's secret, so each service "
            "account is created without keys. Create new ones with `tgcli key create` and give them to whatever used the old ones.", "service-accounts.json"))
    left = [r for r in rows if r.kind == "certificate authority" and r.action == SKIP]
    if left:
        out.append(Notice(
            "certificate authorities", f"Not created ({_many(len(left), 'certificate authority', 'certificate authorities')} in the backup): a backup holds a CA's name and "
            "fingerprint, never its certificate or public key. Give the file with --ca-files and it is used only if its own fingerprint is the "
            "backed-up one. A Gateway that needs one of them is blocked until then.", "certificate-authorities.json"))
    if ca_files and ca_files.problems:
        out.append(Notice("certificate files", "; ".join(ca_files.problems), "--ca-files"))
    return out
