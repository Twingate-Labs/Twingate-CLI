# Changelog

All notable changes to `tgcli` are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [3.0.0] - 2026-10-29

The first tagged release. It covers everything since the 2.0.0 package rebuild in March 2026. If you cloned the repository earlier, your `tgcli -v` also says 2.0.0 but behaves differently; the **Breaking changes** below are what to check before you upgrade.

To install this version: `pip install "git+https://github.com/Twingate-Labs/Twingate-CLI.git@v3.0.0"`. To upgrade a clone: `git pull` then `pip install .`.

### Breaking changes

- **Delete commands ask first and refuse without a terminal.** `account`, `connector`, `group`, `gateway`, `network`, `resource`, `user`, `ca` and `dns-profile` `delete`, and `key delete` / `key revoke`, ask `[y/N]` before acting. `--yes` (`-y`) skips the question. With no terminal to ask on (a script, cron job or pipe) they now **refuse and exit 1 unless you pass `--yes`**. Add `--yes` to any script that deletes. Removing something from a list (`group removeUsers`, `resource access remove`) is not asked about.
- **A write the API refuses now exits 1.** Before, `ok: false` answers printed the row and exited 0. The row is still printed on standard output and the reason goes to standard error as `Error: ...`. `device updateTrust -l` tries every device, then exits 1 if any was refused. Scripts that ignored the exit code will now see failures.
- **Auto-lock moved to `accessPolicy`.** The API deprecated `usageBasedAutolockDurationDays`, so it is gone from every query and from `resource list` / `resource show` JSON. `resource autolock -a N` and `resource access add|set -a N` send an `accessPolicy` instead. `-a` and `-e` are refused for service accounts, which the API does not allow.
- **`resource access_add`, `access_set`, `access_remove` are now `resource access add|set|remove`.** The old names still work as hidden aliases. `access set` with nobody named is refused (it would have removed all access); `--clear` is the explicit way to do that.
- **`policy update --set-groups ""` is refused.** The API silently ignores an empty group list. Use `--clear-groups`.
- **`key create` CSV output had its columns misaligned** (`id` held the key name, `status` held the token). They are in the right columns now, so anything that parsed the old output needs updating. JSON output was always correct.
- **List and show commands now return every item.** `group list`, `network list` and the other read commands used to drop nested items past the 50th (a group's users, a network's resources). They now follow every page, so output can be longer than before.
- **Output is always UTF-8**, including when redirected on Windows.

### Added

- **`tgcli import`**: create Remote Networks, groups with members, and resources with group and service account access from CSV files or from a `tgcli backup` folder, and set device trust by serial number. It is a dry run unless you pass `--execute`. Existing objects are only topped up; `--sync` changes them to match the file and `--prune` removes what the file leaves out. Synced groups are never touched. CSV templates are in `examples/import`.
- **`tgcli backup`**: save groups, users, resources, connectors, Remote Networks, devices, service accounts (with each key's name, status and dates), Security Policies, DNS Filtering profiles, Gateways and Certificate Authorities as JSON, with a manifest of counts and checksums. Every list is followed to its end and checked against the API's own total. A type the API refuses is left out and reported as `NOT READ`; the rest is still written. A read-only API key is enough.
- **`tgcli backup diff`**: compare two backups of the same tenant offline. Reports what was added, removed or changed, matched by ID, ignoring fields that change on their own. `--json`, `--exit-code`, `--include-volatile`.
- **Names as well as IDs** for `-g`, `-p` and `-s` on `resource create` and the access commands. `resource create -g` grants access in one step, `-p` is optional, and a hint is printed when nobody has access yet.
- **`group migrate`**: converts synced groups to manual groups. `--group` migrates one group, the Security Policy is copied, and each resource's own access settings (policy, access policy, approval mode, expiry) are copied too. An expired grant is not migrated.
- **Shell completion** for session names and `group migrate --group` (zsh tested).
- **Resources**: `resource disable` / `enable`, bypass (`BYPASS_TWINGATE`) routing, `resource list --detail`, a `type` column, and access grants with their expiry in `resource show`.
- **Gateway-backed resources and infrastructure**: `ssh-resource`, `webapp-resource` and `k8s-resource` create and update; `gateway` and `ca` (X.509 and SSH) commands; `dns-profile` create and delete.
- **Devices and access**: `device list` filters, `--idsonly` and `--fileofids`, `device unarchive`, device posture checks, `access-request` list, show, approve and reject, `policy update`, `connector delete`.
- **Service accounts and keys**: `key list`, `key expiring`, `key rotate`, `account rename`, `account listKeys`.
- All eight user roles are accepted.

### Fixed

- `group migrate` crashed or misreported its writes, and could fail on non-ASCII group names after the groups were already created.
- Five write-command bugs found by checking against a real tenant: the exit code of refused writes, the misaligned `key create` columns, `key rotate` progress going to standard output, `resource create` requiring `-p`, and `policy update` ignoring an empty group list (see the breaking changes above).
- Windows: reports, redirected output and the files `tgcli` reads (including UTF-16 and byte-order-marked files from PowerShell 5.1) no longer fail on non-ASCII text.
- `gateway delete` of an ID that does not exist now says so instead of reporting success.
- `dnssec` against the current DNS Filtering API.

### Notes

- Windows is documented but has had little testing; please report problems.
- There is no default session: every command that talks to Twingate needs `-s <session>`.
