"""Device posture commands."""

from __future__ import annotations

import typer

from tgcli.commands._common import get_client, run_query
from tgcli.output.transformers import posture as t
from tgcli.queries import posture as q

app = typer.Typer(help="Inspect Device Posture status.")


@app.command("check")
def posture_check(
    itemid: str = typer.Option(..., "-i", "--itemid", help="Device ID."),
) -> None:
    """Fetch the live posture status of a device.

    Returns all property checks (hardDriveEncryption, screenLockPasscode,
    firewall, biometric, antivirus, osVersion) and TrustProviderVerification
    results for CrowdStrike, Jamf, Kandji, Intune, SentinelOne, 1Password,
    and manual verification.
    """
    run_query(get_client(), q.DEVICE_POSTURE_CHECK, {"deviceID": itemid}, t.get_device_posture_as_csv)
