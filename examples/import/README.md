# Import templates

Starting points for `tgcli import`. Copy this folder, edit the files, and run:

```bash
tgcli -s <session> import ./your-copy              # dry run: nothing is changed, a report CSV is written
tgcli -s <session> import ./your-copy --execute    # apply it
```

- `resources.csv` has five example rows: two network resources, and one each of SSH, web app and Kubernetes. The Remote Network, Security Policy and group names in them are placeholders: replace them with the exact names in your tenant (capitals matter), or the rows show as `blocked` in the dry run.
- `remote-networks.csv`, `groups.csv`, `service-accounts.csv`, `gateways.csv` and `devices.csv` are header-only, so a copy of this folder never creates anything you did not add. Delete any file you do not need.
- `service-accounts.csv` is a list of names (made without keys). `gateways.csv` makes Gateways: `address`, the Remote Network, and the **names** of the X.509 and (optional) SSH certificate authorities, which must already exist in the tenant (`tgcli ca create`). Certificate authorities and DNS profiles are JSON only (`certificate-authorities.json`, `dns-profiles.json`, in the shape `tgcli backup` writes): there is no template, and a CA from a backup needs `--ca-files`.
- A resource's `groups` cell is group names separated by `;`; `Group=Policy` gives that group its own Security Policy. `service_accounts` is service account names separated by `;` (they must already exist, and take no per-grant policy, auto-lock or expiry).
- `approver_groups` is group names separated by `;`: the groups that approve access requests for the resource. Leave it blank to state nothing.
- `tcp_ports` / `udp_ports`: `*` or blank is every port, `none` is no ports, otherwise a list like `80;443;8000-8100`.
- The last eight columns (`type` to `headers`) are only for SSH, web app and Kubernetes resources; leave them blank for a network resource. `gateway` is the address of a Gateway that already exists in the tenant (`tgcli gateway list`) or that `gateways.csv` makes in the same run.

- By default an import only adds to what exists. `--sync` also changes existing resources, grants and group policies to match the file, and `--prune` (with `--sync`) removes the access, members and tags the file leaves out. A **blank cell states nothing**, so `--sync` leaves that setting alone; both are dry runs until `--execute`.

Every column is explained in the `import` section of the main README.
