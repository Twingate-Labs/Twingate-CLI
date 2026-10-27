# Import templates

Starting points for `tgcli import`. Copy this folder, edit the files, and run:

```bash
tgcli -s <session> import ./your-copy              # dry run: nothing is changed, a report CSV is written
tgcli -s <session> import ./your-copy --execute    # apply it
```

- `resources.csv` has two example rows. The Remote Network, Security Policy and group names in them are placeholders: replace them with the exact names in your tenant (capitals matter), or the rows show as `blocked` in the dry run.
- `remote-networks.csv`, `groups.csv` and `devices.csv` are header-only, so a copy of this folder never creates anything you did not add. Delete any file you do not need.
- A resource's `groups` cell is group names separated by `;`; `Group=Policy` gives that group its own Security Policy. `service_accounts` is service account names separated by `;` (they must already exist, and take no per-grant policy, auto-lock or expiry).
- `tcp_ports` / `udp_ports`: `*` or blank is every port, `none` is no ports, otherwise a list like `80;443;8000-8100`.

Every column is explained in the `import` section of the main README.
