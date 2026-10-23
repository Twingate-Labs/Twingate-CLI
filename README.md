# Twingate Admin CLI

A command-line interface for the [Twingate](https://www.twingate.com) Admin API. Manage your resources, devices, users, groups, connectors, networks, service accounts, and more — directly from your terminal.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Global Options](#global-options)
- [Output Formats](#output-formats)
- [Multiple Sessions](#multiple-sessions)
- [Shell completion](#shell-completion)
- [Commands](#commands)
  - [auth](#auth)
  - [device](#device)
  - [resource](#resource)
  - [ssh-resource, webapp-resource, k8s-resource](#gateway-backed-resources)
  - [connector](#connector)
  - [group](#group)
  - [user](#user)
  - [network](#network)
  - [account (service accounts)](#account)
  - [key](#key)
  - [policy](#policy)
  - [access-request](#access-request)
  - [gateway](#gateway)
  - [ca (certificate authorities)](#ca)
  - [dnssec](#dnssec)
  - [dns-profile](#dns-profile)
  - [mappings](#mappings)
  - [backup](#backup)
  - [import](#import)
- [Rate Limiting](#rate-limiting)
- [Development](#development)

---

## Requirements

- Python **3.9** or later
- A Twingate account with an [Admin API token](https://docs.twingate.com/docs/api-overview)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Twingate-Labs/Twingate-CLI.git
cd Twingate-CLI

# 2. (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# 3. Install
pip install .
```

The `tgcli` command is now available in your shell.

> **Linux headless / CI environments**
> `tgcli` stores credentials in your OS keychain via the `keyring` library. On headless Linux you may need a fallback backend:
> ```bash
> pip install keyrings.alt
> export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
> ```

### Windows

`tgcli` is pure Python and should run on Windows, but it is developed and tested on macOS and has not yet been tested on Windows. If something does not work, please report it.

```powershell
git clone https://github.com/Twingate-Labs/Twingate-CLI.git
cd Twingate-CLI
py -3 -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell   (cmd.exe: .venv\Scripts\activate.bat)
pip install .
```

- **PowerShell blocks `Activate.ps1`?** If it says "running scripts is disabled on this system", allow scripts for the current window only with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then activate again.
- **Credentials** are kept in Windows Credential Manager (look for entries mentioning `tgcli`), as the Keychain is used on macOS.
- **The examples in this README are written for bash.** Where a command continues on the next line with `\`, use a backtick `` ` `` at the end of the line in PowerShell, `^` in cmd.exe, or put the command on one line. Commands that use `$(...)`, `head`, `grep` or `cron` need PowerShell equivalents (Task Scheduler instead of cron).
- **Saving output to a file or piping it (`> file.csv`)?** Set UTF-8 first, in PowerShell `$env:PYTHONUTF8 = "1"` (cmd.exe: `set PYTHONUTF8=1`). Without it, CSV and table output can fail with a `UnicodeEncodeError` when a name contains characters outside your Windows code page (Greek, Cyrillic, Chinese, Japanese, emoji, ...). JSON output is not affected. `tgcli backup` writes its own UTF-8 files and is not affected.
- **Windows PowerShell 5.1 saves `>` redirection as UTF-16.** For plain UTF-8 files, use PowerShell 7 (`pwsh`), or `| Out-File -Encoding utf8 file.csv` in 5.1.
- **`scripts/disable_offline_resources.sh`** is a bash script. Run it from Git Bash or WSL.

---

## Quick Start

```bash
# Log in — stores your credentials in the OS keychain under a session name you choose (-s)
tgcli auth login -a tgp_xxxxxxxxxxxxxxxxxxxx -t acme -s acme

# Verify it worked
tgcli -v                       # tgcli version 2.0.0
tgcli -s acme resource list    # list all resources
```

Your Twingate **tenant name** is the subdomain of your Twingate URL.
e.g. for `acme.twingate.com` the tenant name is `acme`.

> **Every command that talks to Twingate needs `-s <session>`. There is no default session.**
> Put `-s` before the command, as above. If you leave `-s` off `auth login`, `tgcli` makes up a random session name, and you then have to pass that name with `-s` every time (`tgcli auth list` shows it). Naming your session when you log in avoids that.
>
> To keep the examples in this README short, most of them leave `-s <session>` out. Add it: `tgcli resource list` is really `tgcli -s acme resource list`.

---

## Shell completion

```bash
tgcli --install-completion      # then restart your shell
```

Press TAB to complete commands, subcommands and flags. Completion is provided for zsh, bash (4.4 or newer; the bash 3.2 that ships with macOS is not supported), fish and PowerShell, and has been tested with zsh. Two options also complete their values:

- **`-s` / `--session`** completes your saved session names.
- **`group migrate --group`** completes the names of the groups it can migrate (active Synced Groups). A name shared by several groups is offered as an ID instead, because `migrate` will not accept an ambiguous name. This asks the Twingate API, so type `-s <session>` first, as in `tgcli -s prod group migrate --group <TAB>`. Without a session it offers nothing.

Notes:
- The group names are cached for 2 minutes in `~/.cache/tgcli` (`%LOCALAPPDATA%\tgcli` on Windows), in files only you can read, so repeated TAB presses do not call the API each time.
- Completion never prints errors. If the API cannot be reached or is rate-limiting, it offers the last list it saved, or nothing.
- If `--install-completion` says "Shell not supported" (it detects your shell from the parent process), generate the script yourself and load it from your shell's startup file. For zsh, add `eval "$(_TGCLI_COMPLETE=source_zsh tgcli)"` (use `source_bash` for bash). The same variable with `source_fish` or `source_powershell` prints the script for those shells.

---

## Global Options

These flags go **before** the command name and apply to every call:

| Flag | Short | Description | Default |
|---|---|---|---|
| `--session` | `-s` | Session to use. **Required** for every command that contacts Twingate; there is no default session | none |
| `--format` | `-f` | Output format: `JSON`, `CSV`, `DF` | `JSON` |
| `--log` | `-l` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `ERROR` |
| `--version` | `-v` | Print version and exit | |

```bash
tgcli -s staging -f CSV device list
```

---

## Output Formats

Every command supports three output formats:

```bash
tgcli resource list              # JSON (default)
tgcli -f CSV resource list       # CSV
tgcli -f DF resource list        # Pandas DataFrame (tabular, great for terminals)
```

---

## Multiple Sessions

You can manage several Twingate tenants at once by naming your sessions:

```bash
# Log in to two tenants
tgcli auth login -a tgp_xxx -t acme -s prod
tgcli auth login -a tgp_yyy -t acme-staging -s staging

# Use them with -s (required, even if you only have one session)
tgcli -s prod    resource list
tgcli -s staging resource list

# See all saved sessions
tgcli auth list

# Log out of a specific session
tgcli auth logout -s staging
```

---

## Commands

### auth

Manage authentication sessions.

```bash
# Log in (saves credentials to OS keychain). Always name the session with -s:
tgcli auth login -a tgp_xxxx -t acme -s my-session
# Without -s a random session name is generated, and you must then pass that name with -s on every command.

# List all saved sessions
tgcli auth list

# Log out (-s is required: there is no default session)
tgcli auth logout -s my-session
```

---

### device

Manage Twingate devices and the serial-number allowlist.

```bash
# List all devices
tgcli device list

# Filter server-side (filters combine with AND)
tgcli device list --untrusted
tgcli device list --trusted --state ACTIVE            # --state: ACTIVE, ARCHIVED, BLOCKED (repeatable)
tgcli device list --serial-number "C02XYZ123"
tgcli device list --user-id "VXNlcjoxMjM="            # repeatable

# IDs only, and diff against a saved list of IDs
tgcli -f CSV device list --idsonly
tgcli device list --fileofids known_ids.txt           # prints IDs "new" to the tenant and "missing" from it

# Show a specific device
tgcli device show -i "RGV2aWNlOjE5MzI2OQ=="

# Update trust status
tgcli device updateTrust -i "RGV2aWNlOjE5MzI2OQ==" -t True
tgcli device updateTrust -i "RGV2aWNlOjE5MzI2OQ==" -t False

# Update trust for multiple devices at once
tgcli device updateTrust -l "RGV2aWNlOjE5MzI2OQ==,RGV2aWNlOjE5MzI3MA==" -t True

# Block / unblock / archive / unarchive a device
tgcli device block   -i "RGV2aWNlOjE5MzI2OQ=="
tgcli device unblock -i "RGV2aWNlOjE5MzI2OQ=="
tgcli device archive -i "RGV2aWNlOjE5MzI2OQ=="
tgcli device unarchive -i "RGV2aWNlOjE5MzI2OQ=="

# --- Serial number allowlist ---
tgcli device snumber list
tgcli device snumber add    -n "SN001,SN002,SN003"
tgcli device snumber remove -n "SN001"

# --- Get Posture Checks ---
tgcli device posture -i "RGV2aWNlOjE5MzI2OQ=="

# --- Check Internet Security Client Configuration (e.g. Machine Key deployment) ---
tgcli device show -i "RGV2aWNlOjE5MzI2OQ=="       # see the internetSecurityConfiguration field
tgcli -f CSV device list                          # export all devices with that column included
```

`device list` / `device show` include an `internetSecurityConfiguration` field reporting each device's [Internet Security Client Configuration](https://www.twingate.com/docs/internet-security-client-configuration) state — used to see which devices have a Machine Key deployed so Internet Security features (e.g. DNS filtering) keep running while the user is signed out.

---

### resource

Manage Twingate resources and their access controls.

```bash
# List / show. Both have a "type" column: NETWORK, SSH, WEB_APP or KUBERNETES.
# `show` (and `list --detail`) add, after the original columns: the access policy (mode, duration), the
# approval mode, approver groups (IDs, plus names in the same order) and, for Gateway-backed types, the
# gateway, upstream/downstream ports (plus TLS modes for web apps) and the cluster ref (Kubernetes).
# Columns that don't apply to a resource's type are blank. `list` leaves the extras out by default because
# they make it slower on large tenants (about 13% at 144 resources).
tgcli resource list
tgcli resource list --detail              # (-d) the extra columns described above
tgcli resource show -i "UmVzb3VyY2U6MQ=="

# List only disabled (or only enabled) resources
tgcli resource list -a false
tgcli resource list -a true

# Create a resource (-r Remote Network, -p Security Policy — both required; each an ID or an exact name)
tgcli resource create \
  -a 10.0.0.0/24 \
  -n "Internal Network" \
  -r "UmVtb3RlTmV0d29yazox" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# The same by name, and give two groups access in the same command (-g takes IDs or names)
tgcli resource create \
  -a app.internal.example.com \
  -n "Internal App" \
  -r "Cloud Applications" \
  -p "Default Policy" \
  -g "Engineering,Ops"

# Create with TCP port restriction and a security policy
tgcli resource create \
  -a app.internal.example.com \
  -n "Internal App" \
  -r "UmVtb3RlTmV0d29yazox" \
  -t RESTRICTED \
  -c "[[443,443],[8080,8080]]" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# Create a bypass resource (traffic connects directly, skipping Twingate)
tgcli resource create \
  -a app.internal.example.com \
  -n "Bypass App" \
  -r "UmVtb3RlTmV0d29yazox" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ==" \
  -m BYPASS_TWINGATE

# Delete a resource
tgcli resource delete -i "UmVzb3VyY2U6MQ=="

# Assign a resource to a different remote network
tgcli resource assignNetwork -i "UmVzb3VyY2U6MQ==" -n "UmVtb3RlTmV0d29yazoy"

# Update resource visibility
tgcli resource visibility -i "UmVzb3VyY2U6MQ==" -v True
tgcli resource visibility -i "UmVzb3VyY2U6MQ==" -v False

# Update address or alias
tgcli resource address -i "UmVzb3VyY2U6MQ==" -a 10.0.1.0/24
tgcli resource alias   -i "UmVzb3VyY2U6MQ==" -a myapp.internal

# Update security policy
tgcli resource policy -i "UmVzb3VyY2U6MQ==" -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# Update routing mode on an existing resource
tgcli resource routing -i "UmVzb3VyY2U6MQ==" -m BYPASS_TWINGATE
tgcli resource routing -i "UmVzb3VyY2U6MQ==" -m THROUGH_TWINGATE

# Usage-based autolock (disable with -a -1)
tgcli resource autolock -i "UmVzb3VyY2U6MQ==" -a 7
tgcli resource autolock -i "UmVzb3VyY2U6MQ==" -a 30 -r True   # auto-approve

# Auto-approve mode
tgcli resource autoapprove -i "UmVzb3VyY2U6MQ==" -r True

# Enable / disable a resource
tgcli resource enable  -i "UmVzb3VyY2U6MQ=="
tgcli resource disable -i "UmVzb3VyY2U6MQ=="

# --- Access control: `resource access add | set | remove` ---

# Add group access (non-destructive). Groups, policies and service accounts can be IDs or exact names
tgcli resource access add -i "UmVzb3VyY2U6MQ==" \
  -g "R3JvdXA6Mw==" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="
tgcli resource access add -i "UmVzb3VyY2U6MQ==" -g "Engineering" -p "Strict Policy"

# A different policy per group: give one -p per group, in the same order
tgcli resource access add -i "UmVzb3VyY2U6MQ==" -g "Engineering,Ops" -p "Strict Policy,Default Policy"

# Add service account access with an expiry date
tgcli resource access add -i "UmVzb3VyY2U6MQ==" \
  -s "U2VydmljZUFjY291bnQ6MQ==" \
  -e "2026-12-31T23:59:59Z"

# Remove access for a group or service account
tgcli resource access remove -i "UmVzb3VyY2U6MQ==" -g "R3JvdXA6MQ=="
tgcli resource access remove -i "UmVzb3VyY2U6MQ==" -g "Engineering" -s "ci-bot"

# Replace ALL access with exactly this list (destructive: anything not listed loses access)
tgcli resource access set -i "UmVzb3VyY2U6MQ==" -g "R3JvdXA6MQ==,R3JvdXA6Mg=="

# Remove ALL access. `access set` with nobody named is refused; --clear says you mean it
tgcli resource access set -i "UmVzb3VyY2U6MQ==" --clear
```

**Names or IDs.** `-r`, `-p`, `-g` and `-s` on `resource create` and the three `resource access` commands accept either an ID or the object's **exact name** (capitals matter). Several values can be comma-separated or you can repeat the flag (`-g Engineering -g Ops`).
- An ID is used as given, with no extra request, so scripts that pass IDs behave exactly as before. A name costs one extra lookup per kind (a fraction of a second).
- A name that matches nothing, or matches more than one object, is an error and **nothing is changed**. All the problems are listed together, and an ambiguous name shows the matching IDs so you can pick one.
- A name containing a comma cannot be given by name (the comma splits the list); use its ID.
- Other commands, including `ssh-resource`, `webapp-resource`, `k8s-resource` and the rest of `resource`, still take IDs only.

**Create a resource and give groups access.** A new resource can be reached by nobody until a group (or service account) has access, so there are two ways to do it:

```bash
# One step: create the resource and give groups access. -p is the resource's own Security Policy
tgcli -s acme resource create -a app.internal.example.com -n "Internal App" \
  -r "Cloud Applications" -p "Default Policy" -g "Engineering,Ops"

# Two steps, when you need a different policy per group, service accounts, an expiry or autolock
tgcli -s acme resource create -a app.internal.example.com -n "Internal App" -r "Cloud Applications" -p "Default Policy"
tgcli -s acme resource access add -i <the id it printed> -g "Engineering" -p "Strict Policy"
tgcli -s acme resource access add -i <the id it printed> -g "Ops" -e "2026-12-31T23:59:59Z"
```

If `resource create` is run without `-g`, it prints a reminder to **stderr** (so piped JSON/CSV on stdout is unaffected) with the exact `access add` command for the new resource. To find a resource's ID later, use `tgcli resource list`; `tgcli resource show -i <id>` lists who has access.

**Changing access safely.** `access add` only adds. `access set` **replaces** the whole list, so anything you leave out loses access; to protect against a typo it refuses to run when you name nobody, and removing everyone's access takes the explicit `--clear`. `access add` and `access remove` likewise require at least one group (`-g`) or service account (`-s`). The older spellings `access_add`, `access_set` and `access_remove` still work (they are the same commands, no longer shown in `--help`), so existing scripts keep running.

**Protocol flags for `resource create`:**

| Flag | Description | Default |
|---|---|---|
| `-t` | TCP policy: `ALLOW_ALL` or `RESTRICTED` | `ALLOW_ALL` |
| `-c` | TCP port ranges JSON, e.g. `[[22,22],[443,446]]` | `[]` |
| `-u` | UDP policy: `ALLOW_ALL` or `RESTRICTED` | `ALLOW_ALL` |
| `-d` | UDP port ranges JSON | `[]` |
| `-i` | Disable ICMP | `false` |
| `-m` | Routing mode: `THROUGH_TWINGATE` or `BYPASS_TWINGATE` | `THROUGH_TWINGATE` |

---

### Gateway-backed resources

SSH, Web App and Kubernetes resources have their own `create`/`update` commands. List, show, delete and enable/disable them with the regular [`resource`](#resource) commands.

```bash
# SSH — a Gateway is required
tgcli ssh-resource create -n "Bastion" -a "bastion.corp.internal" -r "<network-id>" -w "<gateway-id>" \
  --upstream-port 22 --downstream-port 22
tgcli ssh-resource update -i "<resource-id>" --active false

# Web app — gateway and both ports are required; TLS modes and header rewrites are optional
tgcli webapp-resource create -n "Grafana" -a "grafana.corp.internal" -r "<network-id>" -w "<gateway-id>" \
  --upstream-port 3000 --upstream-tls NONE --downstream-port 443 --downstream-tls TLS13 \
  --header "X-Forwarded-User=twingate"
tgcli webapp-resource update -i "<resource-id>" --upstream-port 8443 --upstream-tls VERIFY_FULL

# Kubernetes — gateway is optional
tgcli k8s-resource create -n "prod-cluster" -a "k8s.corp.internal" -r "<network-id>" \
  --clusterref prod --upstream-port 6443 --downstream-port 443
```

Shared options: `-l` alias, `-p` policy ID, `-g` group IDs, `-v` visible (true/false). On `update`, only the options you pass are changed, and these are also available: `-n` name, `-a` address, `-r` network, `-w` gateway, `--active true|false`, `--add-groups`, `--remove-groups`.

- TLS: `--upstream-tls` is `VERIFY_FULL`, `VERIFY_CA`, `INSECURE` or `NONE`; `--downstream-tls` is `TLS13` or `NONE`. On `update`, a TLS option needs its matching `--...-port`.
- On `webapp-resource update`, `--header` **replaces** the whole list of header rewrites.
- Not exposed here: protocol/port restrictions, tags, access-policy modes and approver groups.

---

### connector

Manage Twingate connectors.

```bash
# List / show
tgcli connector list
tgcli connector show -i "Q29ubmVjdG9yOjE="

# Create a connector in a remote network
tgcli connector create \
  -i "UmVtb3RlTmV0d29yazox" \
  -c "my-connector" \
  -s true

# Rename a connector
tgcli connector rename -i "Q29ubmVjdG9yOjE=" -n "new-name"

# Generate new access/refresh tokens
tgcli connector generateTokens -i "Q29ubmVjdG9yOjE="

# Enable/disable status email notifications
tgcli connector updateNotifications -i "Q29ubmVjdG9yOjE=" -s true
tgcli connector updateNotifications -i "Q29ubmVjdG9yOjE=" -s false

# Delete a connector (a deployed connector stops working; no confirmation prompt)
tgcli connector delete -i "Q29ubmVjdG9yOjE="
```

---

### group

Manage Twingate groups and their members.

```bash
# List / show
tgcli group list
tgcli group show -i "R3JvdXA6MQ=="

# Create a group (members, resources, and security policy are optional)
tgcli group create -g "Engineering"
tgcli group create -g "DevOps" \
  -u "VXNlcjox,VXNlcjoy" \
  -r "UmVzb3VyY2U6MQ==,UmVzb3VyY2U6Mg==" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# Delete a group
tgcli group delete -i "R3JvdXA6MQ=="

# Add / remove users
tgcli group addUsers    -g "R3JvdXA6MQ==" -u "VXNlcjox,VXNlcjoy"
tgcli group removeUsers -g "R3JvdXA6MQ==" -u "VXNlcjox"

# Add / remove resources
tgcli group addResources    -g "R3JvdXA6MQ==" -r "UmVzb3VyY2U6MQ==,UmVzb3VyY2U6Mg=="
tgcli group removeResources -g "R3JvdXA6MQ==" -r "UmVzb3VyY2U6MQ=="

# Assign a security policy to a group
tgcli group assignPolicy -g "R3JvdXA6MQ==" -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# Migrate all active Synced Groups to new Manual Groups (dry run by default)
tgcli group migrate
tgcli group migrate --execute

# Migrate only some groups: by ID or exact name, repeat --group for several
tgcli group migrate --group "Engineering"
tgcli group migrate --group "Engineering" --group "R3JvdXA6MQ==" --execute

# Customize the migration
tgcli group migrate --execute \
  --name-suffix " (Manual)" \
  --no-copy-security-policy \
  --report my_report.csv
```

`group migrate` creates an empty Manual Group for each active Synced Group (named `<name><suffix>`), then adds the source group's members and resources in batches of 200. It copies the source group's Security Policy unless you pass `--no-copy-security-policy`. It reuses an existing Manual Group if one with the target name already exists (so a re-run does not create duplicates), skips inactive Synced Groups, and writes a timestamped CSV report of every group processed (or use `--report` for a custom path).

- A failure on one group is recorded in the report and the rest continue; the command then exits 1.
- **Not copied:** settings on a group's access to an individual resource (a different policy, access policy or expiry for that grant). Only the resource itself is added, so check any such grants on the new group.
- With `--group`, only the groups you name are read and migrated, and the report lists only those. Every name is checked before anything is read or written: a name that matches no group, matches several active Synced Groups (use the ID), or names a group that cannot be migrated (a Manual group, or an inactive one) stops the run with an error rather than being skipped. Without `--group`, `--execute` acts on every active Synced Group, so run the dry run first.

---

### user

Manage Twingate users.

```bash
# List / show
tgcli user list
tgcli user show -i "VXNlcjox"

# Create a user and send an invitation email
tgcli user create \
  -e alice@example.com \
  -f Alice \
  -l Smith \
  -r MEMBER

# Create without sending the invitation
tgcli user create -e bob@example.com -l Jones -r DEVOPS -s False

# Update role (see the roles table below)
tgcli user role -i "VXNlcjox" -r ADMIN
tgcli user role -i "VXNlcjox" -r HELPDESK

# Enable or disable a user
tgcli user state -i "VXNlcjox" -s ACTIVE
tgcli user state -i "VXNlcjox" -s DISABLED

# Reset MFA
tgcli user resetmfa -i "VXNlcjox"

# Delete a user
tgcli user delete -i "VXNlcjox"
```

**Roles** (`-r` on `user create` and `user role`; case-insensitive):

| Role | Access |
|---|---|
| `ADMIN` | Full access to the Admin Console |
| `SUPPORT` | Read-only access to the Admin Console |
| `DEVOPS` | Full access to the Network tab, read-only access to the rest of the Admin Console |
| `INTERNET_SECURITY` | Full access to the Internet Security tab, read-only access to the rest of the Admin Console |
| `HELPDESK` | Read-only Admin Console access with MFA reset and device verification |
| `ACCESS_REVIEWER` | Access to Resource requests only |
| `BILLING` | Access to Billing functions only |
| `MEMBER` | No access to the Admin Console |

Which roles you can assign can depend on your Twingate plan.
---

### network

Manage Twingate remote networks.

```bash
# List / show
tgcli network list
tgcli network show -i "UmVtb3RlTmV0d29yazox"

# Create a remote network
tgcli network create -n "AWS US-East" -a true -l AWS
tgcli network create -n "HQ Office"   -a true -l ON_PREMISE

# Locations: AWS | AZURE | GOOGLE_CLOUD | ON_PREMISE | OTHER

# Delete a network
tgcli network delete -i "UmVtb3RlTmV0d29yazox"

# Activate / deactivate
tgcli network updateState -i "UmVtb3RlTmV0d29yazox" -a true
tgcli network updateState -i "UmVtb3RlTmV0d29yazox" -a false

# Rename
tgcli network updateName -i "UmVtb3RlTmV0d29yazox" -n "AWS EU-West"

# Update location
tgcli network updateLocation -i "UmVtb3RlTmV0d29yazox" -l AZURE
```

---

### account

Manage Twingate service accounts.

```bash
# List / show
tgcli account list
tgcli account show -i "U2VydmljZUFjY291bnQ6MQ=="

# Create a service account (optionally pre-assign resources)
tgcli account create -n "CI/CD Bot"
tgcli account create -n "Monitoring" -r "UmVzb3VyY2U6MQ==,UmVzb3VyY2U6Mg=="

# Add / remove resources
tgcli account addResources    -i "U2VydmljZUFjY291bnQ6MQ==" -r "UmVzb3VyY2U6Mw=="
tgcli account removeResources -i "U2VydmljZUFjY291bnQ6MQ==" -r "UmVzb3VyY2U6Mw=="

# Rename a service account
tgcli account rename -i "U2VydmljZUFjY291bnQ6MQ==" -n "New Name"

# List all keys for a specific service account
tgcli account listKeys -i "U2VydmljZUFjY291bnQ6MQ=="

# Delete a service account
tgcli account delete -i "U2VydmljZUFjY291bnQ6MQ=="
```

---

### key

Manage service account keys.

```bash
# Show key details
tgcli key show -i "S2V5OjE="

# Create a key (expiration in days, 0 = never expires)
tgcli key create -n "deploy-key" -i "U2VydmljZUFjY291bnQ6MQ==" -e 90
tgcli key create -n "permanent"  -i "U2VydmljZUFjY291bnQ6MQ==" -e 0

# Rename a key
tgcli key rename -i "S2V5OjE=" -n "new-key-name"

# Revoke a key (disables it but keeps the record)
tgcli key revoke -i "S2V5OjE="

# Permanently delete a key
tgcli key delete -i "S2V5OjE="

# Rotate a key: creates a new key on the same Service Account, then revokes the old one
tgcli key rotate -i "S2V5OjE="
tgcli key rotate -i "S2V5OjE=" -e 90 -n "deploy-key-2026Q3"

# List all keys across all service accounts, optionally filtered by status
tgcli key list
tgcli key list -s REVOKED

# List active keys expiring within N days (default 30)
tgcli key expiring
tgcli key expiring -d 7
```

`key rotate` prints the new key's secret token — save it immediately, it can't be retrieved again. There's no native rotate mutation in the Twingate API; this orchestrates create-then-revoke. If creating the new key fails, the old key is left untouched. If the new key is created but revoking the old one fails, both stay active and the old key's ID is reported so you can revoke it manually.

---

### policy

Manage Twingate security policies. The API only lets you change which groups a policy is assigned to, not the policy's rules.

```bash
# List all security policies
tgcli policy list

# Show a specific policy
tgcli policy show -i "U2VjdXJpdHlQb2xpY3k6MQ=="

# Assign / unassign groups
tgcli policy update -i "U2VjdXJpdHlQb2xpY3k6MQ==" --add-groups "R3JvdXA6MQ==,R3JvdXA6Mg=="
tgcli policy update -i "U2VjdXJpdHlQb2xpY3k6MQ==" --remove-groups "R3JvdXA6Mw=="

# Replace the policy's entire group assignment (cannot be combined with --add-groups/--remove-groups)
tgcli policy update -i "U2VjdXJpdHlQb2xpY3k6MQ==" --set-groups "R3JvdXA6MQ=="
```

---

### access-request

Review and resolve resource access requests.

```bash
# List requests (all statuses by default; the API itself only returns PENDING when unfiltered)
tgcli access-request list
tgcli access-request list --status PENDING             # --status: PENDING, APPROVED, REJECTED (repeatable)
tgcli access-request list --user-id "VXNlcjoxMjM=" --resource-id "UmVzb3VyY2U6NDU2"

# Show one request
tgcli access-request show -i "QWNjZXNzUmVxdWVzdDox"

# Approve / reject
tgcli access-request approve -i "QWNjZXNzUmVxdWVzdDox"
tgcli access-request reject  -i "QWNjZXNzUmVxdWVzdDox"
```

---

### gateway

Manage Gateways (Layer 7 privileged-access proxies) and see their remote network and certificate authorities.

```bash
tgcli gateway list
tgcli gateway show -i "R2F0ZXdheTox"

# Create (SSH CA is optional)
tgcli gateway create -n "UmVtb3RlTmV0d29yazox" -a "gateway.example.com:443" -x "<x509-ca-id>" [-s "<ssh-ca-id>"]

# Update — only the options you pass are changed
tgcli gateway update -i "R2F0ZXdheTox" -a "new.example.com:443"
tgcli gateway update -i "R2F0ZXdheTox" -s "<ssh-ca-id>"

# Delete (no confirmation prompt; the API reports success even if the ID doesn't exist)
tgcli gateway delete -i "R2F0ZXdheTox"
```

---

### ca

Manage the X.509 and SSH Certificate Authorities that Gateways use.

```bash
tgcli ca list                      # both types, with a "type" column (X509 / SSH)
tgcli ca show -i "<ca-id>"

# Create from PUBLIC material only (a PEM certificate, or an SSH public key)
tgcli ca create -t x509 -n "Corp X509 CA" --file ./ca.pem
tgcli ca create -t ssh  -n "Vault SSH CA" --file ./ssh_ca.pub

# Delete (type detected automatically; errors if the ID doesn't exist; no confirmation prompt)
tgcli ca delete -i "<ca-id>"
```

---

### dnssec

Manage a single DNS Filtering profile's allow/deny domain lists. Every
profile is identified by ID now that Twingate supports multiple DNS
Filtering profiles per tenant — use [dns-profile](#dns-profile) to find the
ID.

```bash
# Show a profile's allow/deny lists
tgcli dnssec show -i "RG5zRmlsdGVyaW5nUHJvZmlsZTpiZmIzMjM="

# Set a profile's DNS allow list (replaces existing)
tgcli dnssec setAllowList -i "RG5zRmlsdGVyaW5nUHJvZmlsZTpiZmIzMjM=" -d "example.com,internal.corp"

# Set a profile's DNS deny list (replaces existing)
tgcli dnssec setDenyList -i "RG5zRmlsdGVyaW5nUHJvZmlsZTpiZmIzMjM=" -d "ads.example.com,tracking.io"
```

---

### dns-profile

List DNS Filtering profiles and see which Groups (and therefore users) each
one is assigned to.

```bash
# List all DNS Filtering profiles
tgcli dns-profile list

# Show a specific profile, including its allow/deny lists and assigned groups
tgcli dns-profile show -i "RG5zRmlsdGVyaW5nUHJvZmlsZTpiZmIzMjM="

# Create a profile (name only; the API applies its default settings)
tgcli dns-profile create -n "Contractors"

# Delete a profile (errors if the ID doesn't exist; no confirmation prompt; groups on it lose its filtering)
tgcli dns-profile delete -i "RG5zRmlsdGVyaW5nUHJvZmlsZTpiZmIzMjM="
```

To change a profile's allow/deny lists, use [`dnssec`](#dnssec).

---

### mappings

Analyse user-to-resource and user-to-network access mappings.

```bash
# Show which remote networks each user can reach
tgcli mappings user-network

# Show resources accessible to a specific user, optionally matched against an FQDN
# (also flags duplicate/ambiguous Resource definitions across Groups)
tgcli mappings user-resource -e alice@example.com
tgcli mappings user-resource -e alice@example.com -f app.internal.example.com

# Export all mappings to CSV
tgcli -f CSV mappings user-resource -e alice@example.com

# Show which Resources have no live Connector in their Remote Network
# (joins Resources + Connectors client-side via Remote Network ID —
# nothing in the API links a Resource directly to a Connector)
tgcli mappings resource-connectivity
tgcli mappings resource-connectivity --offline-only
```

---

### backup

Save the tenant's current state — groups, users, resources, connectors and remote networks — as JSON files. Read-only.

```bash
tgcli backup                         # ./twingate-backup-<tenant>-<UTC timestamp>/
tgcli backup -o ./backups/acme-weekly
tgcli -s staging backup              # another saved session
```

It writes one file per type plus a manifest:

```
groups.json  users.json  resources.json  connectors.json  remote-networks.json  manifest.json
```

- **Complete lists.** The API returns at most 50 items per page, so every list, including nested ones such as a group's resources or a resource's access, is followed to its end. Each count is then checked against the API's own total; the manifest records the result, and the command exits non-zero if anything doesn't add up (the files are still written).
- **Relationships are saved from both sides** (a group lists its users and each user lists its groups), and IDs are kept, so a backup can be compared against a later one or used to rebuild state.
- **Resources** include their type, protocols, tags, access (groups and service accounts with their policy, access policy, approval mode and expiry), approver groups, and gateway/ports/cluster ref for Gateway-backed types. Deprecated API fields are not included.
- **Secrets are never included.** The API does not return connector tokens or service account keys.
- **Privacy.** The files contain user names and emails. On macOS and Linux the directory is created readable by you only (`0700`/`0600`). **On Windows those permission bits do not apply**, so the files simply inherit the folder's access rights: save backups to a folder only you can read. Keep backups somewhere appropriate.
- **Safe to run unattended.** It never overwrites: an existing output directory is refused. Files are written to `<dir>.partial` and renamed once complete, so an interrupted run leaves no half-finished backup.
- **Not a transaction.** Pages are read one after another, so changes made while it runs may or may not be included. Connector `lastHeartbeatAt` changes about once a minute, so backups taken minutes apart can differ there even if nothing was edited.
- **Not included:** devices, service accounts and their keys, security policies, DNS filtering profiles, gateways and certificate authorities (gateways appear only as references on remote networks).

---

### import

Create Remote Networks, groups (with their members) and resources (with group access), and set device trust by serial number, from a file. **A dry run by default**: nothing is changed until you add `--execute`.

```bash
tgcli -s staging import ./twingate-backup-acme-20261023T101500Z                  # dry run, writes import_report_<timestamp>.csv
tgcli -s staging import ./twingate-backup-acme-20261023T101500Z --execute        # apply it
tgcli -s staging import ./my-files --report ./plan.csv                           # files you wrote yourself
tgcli -s staging import ./groups.csv                                             # one file
```

The input is a folder, or a single file, named `remote-networks`, `groups`, `resources` and `devices`, as `.json` or `.csv` (one or the other per name). A `tgcli backup` folder works as it is, so a backup of one tenant can be loaded into another; `users.json`, `connectors.json` and the manifest are ignored. (A backup has no `devices` file; that one you write yourself.)

**How it matches things**

- Remote Networks and groups by exact name, group members by **email**, Security Policies by name, and resources by **name, Remote Network and address together**. IDs in a backup belong to the tenant it came from and are never used.
- Anything that already exists is **left exactly as it is and only added to**: missing group members, missing resource access. Nothing is ever removed or changed, so you can run the same import again after a failure and it finishes the job, and a second run on a finished import does nothing.
- **Synced Groups are never created, changed or given members** (their members belong to your identity provider). A resource can still be given access to one.
- A name that matches more than one object is never guessed: the row is blocked (or, for an optional extra, left out with a warning). Real tenants can hold several resources with the same name, Remote Network and address; those cannot be told apart, so the second and later ones in a file are blocked (create them by hand).

**What a row can end up as**

| Status | Meaning |
|---|---|
| `would-create` / `would-update` (dry run), `created` / `updated` | What was, or would be, done |
| `exists` | Already there, nothing to add |
| `skipped` | Deliberately not imported (Synced and System groups, SSH / web app / Kubernetes resources) |
| `blocked` | Cannot be made correctly, for example its Remote Network or Security Policy does not exist, or a port list is invalid. Nothing is sent for it |
| `error` / `not-run` | The API refused it, or the run stopped because the credentials were rejected |

A row with a **warning** still goes ahead, but something optional was left out and the report says what: a member whose email is not in this tenant, access for a group that does not exist, a per-group policy that does not exist (it is not replaced by the default), access that has already expired (it is never restored as permanent access). Warnings do not change the exit code; `blocked` and `error` rows exit 1, also on a dry run, so a script can check before applying.

Every row, with its status, detail, warnings, error, the new ID and where in the file it came from, is written to the CSV report (`--report`, default `import_report_<UTC timestamp>.csv`).

**CSV columns** (the first row is the header; unknown columns are an error, so a typo cannot silently drop access)

| File | Columns |
|---|---|
| `remote-networks.csv` | `name` (required), `location` (`AWS`, `AZURE`, `GOOGLE_CLOUD`, `ON_PREMISE`, `OTHER`), `network_type` (`REGULAR`, `EXIT`), `active` |
| `groups.csv` | `name` (required), `members` (emails separated by `;`), `security_policy` |
| `devices.csv` | `serial_number` (required), `trusted` (default `true`) |
| `resources.csv` | `name`, `network`, `address` (all required), `alias`, `tcp_ports`, `udp_ports`, `allow_icmp`, `visible`, `security_policy`, `groups`, `routing_mode` |

- `tcp_ports` / `udp_ports`: `*` or blank means every port, `none` means no ports, otherwise a list like `80;443;8000-8100`.
- `groups`: group names separated by `;`, each optionally followed by `=<Security Policy>` for a per-group policy, for example `Engineering=Strict Policy;Ops`. A group name containing `;` or `=` needs the JSON format.
- True/false columns accept `true`/`false`, `yes`/`no` and `1`/`0`. Empty cells use the API's defaults.

**Device trust by serial number.** `devices.csv` (or `devices.json` with `serialNumber` and `isTrusted`) sets `trusted` on devices that have **already registered** with the tenant; the serial number is matched ignoring case.

- Only devices that are not archived are changed. A serial number that has no device yet, or only archived ones, is `skipped`; to trust a serial number before its device registers, add it to the allowlist with `tgcli device snumber add`.
- One serial number can belong to several devices. Making them trusted is only done when they all belong to **one user**: if the matching devices belong to several users (some VMs and hardware report a generic serial), the row is `blocked` and you pick the device with `tgcli device updateTrust -i`. Making devices **untrusted** applies to all of them.
- After each change the API's reply is checked: if it says the device did not end up with the trust you asked for, the row is an `error`.
- The API refuses to untrust a device whose serial number is **verified** ("Serial number verified Devices cannot be unverified via API"). That row is an `error` showing the API's message, and the device is left as it was.

**Imported from the backup's JSON:** Remote Network location, type and active state; group name, Security Policy and members; for each network resource its address, alias, protocols and ports, visibility, browser shortcut, routing mode, tags, Security Policy, access policy and approval mode, and the access of each group (with its own policy, access policy, approval mode and expiry).

**Not imported yet** (each is reported, never silently dropped): users (they must already exist), connectors, SSH / web app / Kubernetes resources, service account access, approver groups, device posture checks, security policies, DNS filtering profiles, gateways and certificate authorities.

**Rate limits.** The API typically allows about 20 writes a minute. A dry run tells you how many write requests a large import would make; the run pauses when rate limited, and if it gives up part way, run the same command again to finish.

**Encoding:** reports, and CSV input, are UTF-8. Excel may show non-English characters wrongly if you double-click the report; use Data > From Text/CSV and choose UTF-8.

---

## Rate Limiting

The Twingate API enforces rate limits (typically 60 reads/min and 20 writes/min, which may vary by account). The CLI handles this automatically:

- When an HTTP **429 Too Many Requests** response is received, a warning is printed to `stderr` and the request is **automatically retried** after the wait time specified in the API's `Retry-After` header.
- Up to **3 retries** are attempted before the command fails with an error.
- If no `Retry-After` header is present, a default wait of **60 seconds** is used.

Example warning output:

```
⚠  Rate limited by Twingate API. Waiting 42s before retrying (attempt 1/3)...
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest

# Run tests without coverage report (faster)
python -m pytest --no-cov
```

**Project layout:**

```
src/tgcli/
├── client/        # HTTP client, session management, exceptions
├── commands/      # One file per command group (Typer apps)
├── output/        # Formatter + per-entity transformers
├── queries/       # GraphQL query/mutation constants
├── validators/    # Input validation helpers
└── utils/         # Shared utilities (FQDN matching etc.)
tests/
├── commands/      # Command-level integration tests (CliRunner)
├── conftest.py    # Shared fixtures (mock keyring, sample data)
└── test_*.py      # Unit tests
```
