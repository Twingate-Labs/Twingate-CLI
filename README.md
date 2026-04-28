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
- [Commands](#commands)
  - [auth](#auth)
  - [device](#device)
  - [resource](#resource)
  - [connector](#connector)
  - [group](#group)
  - [user](#user)
  - [network](#network)
  - [account (service accounts)](#account)
  - [key](#key)
  - [policy](#policy)
  - [dnssec](#dnssec)
  - [mappings](#mappings)
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

---

## Quick Start

```bash
# Log in — stores your credentials in the OS keychain
tgcli auth login -a acme -t tgp_xxxxxxxxxxxxxxxxxxxx

# Verify it worked
tgcli -v            # tgcli version 2.0.0
tgcli resource list # list all resources
```

Your Twingate **tenant name** is the subdomain of your Twingate URL.
e.g. for `acme.twingate.com` the tenant name is `acme`.

---

## Global Options

These flags go **before** the command name and apply to every call:

| Flag | Short | Description | Default |
|---|---|---|---|
| `--session` | `-s` | Session name to use | `default` |
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
tgcli auth login -a acme -t tgp_xxx -s prod
tgcli auth login -a acme-staging -t tgp_yyy -s staging

# Use them with -s
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
# Log in (saves credentials to OS keychain)
tgcli auth login -a <tenant> -t <api-token>
tgcli auth login -a acme -t tgp_xxxx -s my-session   # named session

# List all saved sessions
tgcli auth list

# Log out
tgcli auth logout                  # default session
tgcli auth logout -s my-session    # named session
```

---

### device

Manage Twingate devices and the serial-number allowlist.

```bash
# List all devices
tgcli device list

# Show a specific device
tgcli device show -i "RGV2aWNlOjE5MzI2OQ=="

# Update trust status
tgcli device updateTrust -i "RGV2aWNlOjE5MzI2OQ==" -t True
tgcli device updateTrust -i "RGV2aWNlOjE5MzI2OQ==" -t False

# Update trust for multiple devices at once
tgcli device updateTrust -l "RGV2aWNlOjE5MzI2OQ==,RGV2aWNlOjE5MzI3MA==" -t True

# Block / unblock / archive a device
tgcli device block   -i "RGV2aWNlOjE5MzI2OQ=="
tgcli device unblock -i "RGV2aWNlOjE5MzI2OQ=="
tgcli device archive -i "RGV2aWNlOjE5MzI2OQ=="

# --- Serial number allowlist ---
tgcli device snumber list
tgcli device snumber add    -n "SN001,SN002,SN003"
tgcli device snumber remove -n "SN001"

# --- Get Posture Checks ---
tgcli device posture -i "RGV2aWNlOjE5MzI2OQ=="
```

---

### resource

Manage Twingate resources and their access controls.

```bash
# List / show
tgcli resource list
tgcli resource show -i "UmVzb3VyY2U6MQ=="

# Create a resource
tgcli resource create \
  -a 10.0.0.0/24 \
  -n "Internal Network" \
  -r "UmVtb3RlTmV0d29yazox"          # Remote Network ID

# Create with TCP port restriction and a security policy
tgcli resource create \
  -a app.internal.example.com \
  -n "Internal App" \
  -r "UmVtb3RlTmV0d29yazox" \
  -t RESTRICTED \
  -c "[[443,443],[8080,8080]]" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="

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

# Usage-based autolock (disable with -a -1)
tgcli resource autolock -i "UmVzb3VyY2U6MQ==" -a 7
tgcli resource autolock -i "UmVzb3VyY2U6MQ==" -a 30 -r True   # auto-approve

# Auto-approve mode
tgcli resource autoapprove -i "UmVzb3VyY2U6MQ==" -r True

# --- Access control ---

# Replace all group/service-account access (destructive)
tgcli resource access_set -i "UmVzb3VyY2U6MQ==" \
  -g "R3JvdXA6MQ==,R3JvdXA6Mg=="

# Add group access (non-destructive)
tgcli resource access_add -i "UmVzb3VyY2U6MQ==" \
  -g "R3JvdXA6Mw==" \
  -p "U2VjdXJpdHlQb2xpY3k6MQ=="

# Add service account access with an expiry date
tgcli resource access_add -i "UmVzb3VyY2U6MQ==" \
  -s "U2VydmljZUFjY291bnQ6MQ==" \
  -e "2026-12-31T23:59:59Z"

# Remove access for a group or service account
tgcli resource access_remove -i "UmVzb3VyY2U6MQ==" -g "R3JvdXA6MQ=="
```

**Protocol flags for `resource create`:**

| Flag | Description | Default |
|---|---|---|
| `-t` | TCP policy: `ALLOW_ALL` or `RESTRICTED` | `ALLOW_ALL` |
| `-c` | TCP port ranges JSON, e.g. `[[22,22],[443,446]]` | `[]` |
| `-u` | UDP policy: `ALLOW_ALL` or `RESTRICTED` | `ALLOW_ALL` |
| `-d` | UDP port ranges JSON | `[]` |
| `-i` | Disable ICMP | `false` |

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
```

---

### group

Manage Twingate groups and their members.

```bash
# List / show
tgcli group list
tgcli group show -i "R3JvdXA6MQ=="

# Create a group (members and resources are optional)
tgcli group create -g "Engineering"
tgcli group create -g "DevOps" \
  -u "VXNlcjox,VXNlcjoy" \
  -r "UmVzb3VyY2U6MQ==,UmVzb3VyY2U6Mg=="

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
```

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

# Update role (ADMIN | DEVOPS | SUPPORT | MEMBER)
tgcli user role -i "VXNlcjox" -r ADMIN

# Enable or disable a user
tgcli user state -i "VXNlcjox" -s ACTIVE
tgcli user state -i "VXNlcjox" -s DISABLED

# Reset MFA
tgcli user resetmfa -i "VXNlcjox"

# Delete a user
tgcli user delete -i "VXNlcjox"
```

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
```

---

### policy

Manage Twingate security policies (read-only via API).

```bash
# List all security policies
tgcli policy list

# Show a specific policy
tgcli policy show -i "U2VjdXJpdHlQb2xpY3k6MQ=="
```

---

### dnssec

Manage Twingate DNS security (filtering) settings.

```bash
# Show current DNS filtering profile
tgcli dnssec show

# Set the DNS allow list (replaces existing)
tgcli dnssec setAllowList -d "example.com,internal.corp"

# Set the DNS deny list (replaces existing)
tgcli dnssec setDenyList -d "ads.example.com,tracking.io"
```

---

### mappings

Analyse user-to-resource and user-to-network access mappings.

```bash
# Show which resources each user can reach
tgcli mappings user-resource

# Show which remote networks each user can reach
tgcli mappings user-network

# Show resource access for a specific user (by email)
tgcli mappings user-resource-detail -e alice@example.com

# Export all mappings to CSV
tgcli -f CSV mappings user-resource
```

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
