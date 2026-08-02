# Twingate CLI - API Gap Analysis

> Generated 2026-08-01 by comparing the Twingate GraphQL API reference
> (https://www.twingate.com/docs/api) against the CLI implementation in
> `src/tgcli/queries/`.

---

## 1. Entirely Missing Entity Types

These API entities have zero CLI coverage -- no queries, no mutations, no commands.

### 1a. Gateway (Access Nodes)

The API exposes a full Gateway lifecycle. The CLI has nothing.

- [ ] `gateway` query -- fetch single Gateway by ID
- [ ] `gateways` query -- list Gateways (paginated)
- [ ] `gatewayCreate` mutation -- create a Gateway (address, remoteNetworkId, x509CAId, sshCAId)
- [ ] `gatewayDelete` mutation -- delete a Gateway
- [ ] `gatewayUpdate` mutation -- update address, remoteNetworkId, sshCAId, x509CAId

### 1b. SSH Resources

Typed resource subtype with dedicated create/update mutations.

- [ ] `sshResourceCreate` mutation -- create SSH Resource (address, gatewayId, upstream/downstream ports, etc.)
- [ ] `sshResourceUpdate` mutation -- update SSH Resource (all standard resource fields + SSH-specific upstream/downstream/gatewayId)

### 1c. Kubernetes Resources

Typed resource subtype with dedicated create/update mutations.

- [ ] `kubernetesResourceCreate` mutation -- create Kubernetes Resource (address, gatewayId, clusterRef, upstream/downstream ports, etc.)
- [ ] `kubernetesResourceUpdate` mutation -- update Kubernetes Resource

### 1d. Web App Resources

Typed resource subtype with dedicated create/update mutations.

- [ ] `webAppResourceCreate` mutation -- create Web App Resource (address, gatewayId, upstream/downstream, requestHeaderRewrites, etc.)
- [ ] `webAppResourceUpdate` mutation -- update Web App Resource

### 1e. Certificate Authorities

Two sub-types: SSH CA and X509 CA, plus a unified read query.

- [ ] `certificateAuthorities` query -- list all CAs (paginated)
- [ ] `certificateAuthority` query -- fetch single CA by ID
- [ ] `sshCertificateAuthorityCreate` mutation -- create SSH CA (name, publicKey)
- [ ] `sshCertificateAuthorityDelete` mutation -- delete SSH CA
- [ ] `x509CertificateAuthorityCreate` mutation -- create X509 CA (name, certificate PEM)
- [ ] `x509CertificateAuthorityDelete` mutation -- delete X509 CA

### 1f. Access Requests

The API exposes access request queries and approval/rejection.

- [ ] `accessRequest` query -- fetch single Access Request by ID
- [ ] `accessRequests` query -- list Access Requests (paginated, filterable)
- [ ] `accessRequestApprove` mutation -- approve an Access Request
- [ ] `accessRequestReject` mutation -- reject an Access Request

---

## 2. Missing Operations on Existing Entities

### 2a. Connectors

- [ ] `connectorDelete` mutation -- the API supports it; the CLI has no delete command

### 2b. Security Policies (currently read-only)

- [ ] `securityPolicyUpdate` mutation -- add/remove/set Group IDs assigned to a policy

### 2c. Service Accounts

- [ ] `serviceAccountUpdate` -- rename (the `name` param). CLI supports add/remove resources but not renaming.
- [ ] `serviceAccountUpdate` -- `resourceIds` (full replace). CLI only supports `addedResourceIds` / `removedResourceIds`, not the full-replace variant.

### 2d. Devices

- [ ] `deviceUnarchive` mutation -- the CLI has `archive` but not `unarchive`

### 2e. Users

- [ ] `userDetailsUpdate` -- update firstName/lastName. The CLI calls `userDetailsUpdate` only for state changes; first/last name updates are not exposed as a command.
- [ ] `userRoleUpdate` -- the API has `ACCESS_REVIEWER` and `BILLING` roles. Verify the CLI supports all six role values (ADMIN, DEVOPS, SUPPORT, ACCESS_REVIEWER, BILLING, MEMBER).

### 2f. Groups

- [ ] `groupUpdate` -- rename (the `name` param). No CLI command to rename a group.
- [ ] `groupUpdate` -- `isActive` flag. No CLI command to activate/deactivate a group.
- [ ] `groupUpdate` -- `userIds` and `resourceIds` (full-replace). CLI only supports additive/removal variants.

### 2g. Remote Networks

- [ ] `remoteNetwork` query supports lookup by `name` (not just `id`). CLI only looks up by ID.
- [ ] Remote Networks now expose a `gateways` edge. The CLI `LIST_NETWORKS`/`SHOW_NETWORK` queries don't fetch gateways.
- [ ] Remote Networks have a `networkType` field (REGULAR, EXIT). Not fetched or surfaced.

---

## 3. Missing Fields / Edges on Existing Queries

### 3a. Resources

- [ ] `tags` -- the LIST query fetches tags, but the CLI has no command to set/update tags via `resourceUpdate(tags:)` or `resourceCreate(tags:)`
- [ ] `isBrowserShortcutEnabled` -- fetched on show, but no CLI command to toggle it via `resourceUpdate(isBrowserShortcutEnabled:)`
- [ ] `accessPolicy` field (AccessPolicy type with `mode` + `durationSeconds`) -- the newer structured access policy. The CLI uses the older `usageBasedAutolockDurationDays` which is deprecated ("Use `accessPolicy` instead")
- [ ] `approverGroups` edge -- not fetched on list/show
- [ ] `name` update via `resourceUpdate` -- no dedicated rename command for resources
- [ ] `protocols` update via `resourceUpdate` -- no command to update port/protocol restrictions after creation
- [ ] `access` edge (unified access connection replacing deprecated `groups`/`serviceAccounts` edges) -- list query uses inline fragments to read access, but show query does not
- [ ] Resource type discrimination -- the API has four resource types (NetworkResource, KubernetesResource, SSHResource, WebAppResource). The CLI treats everything as generic Resource; inline fragments are only used for `routingMode`. The `upstream`/`downstream` port config for typed resources is not surfaced.

### 3b. Users

- [ ] `avatarUrl` field -- not fetched
- [ ] `type` field (MANUAL vs SYNCED) -- not fetched
- [ ] `devices` edge -- users have a devices connection; not fetched or surfaced
- [ ] `isAdmin` field (deprecated, but `role` is used) -- fine, but verify enum completeness

### 3c. Groups

- [ ] `originId` field -- not fetched (useful for synced groups to show IdP origin)
- [ ] `securityPolicy` edge -- not fetched on list/show (only set via assignPolicy)

### 3d. Connectors

- [ ] Filter support -- the API supports `ConnectorFilterInput` on the list query; the CLI doesn't pass filters

### 3e. Devices

- [ ] Filter support -- the API supports `DeviceFilterInput` on the list query; the CLI doesn't pass filters
- [ ] DevicePosture: the `kandji` field is deprecated; use `iru` instead. The CLI fetches `kandji` but not `iru`.

### 3f. Service Accounts

- [ ] Filter support -- the API supports `ServiceAccountFilterInput`; CLI doesn't use it

### 3g. Security Policies

- [ ] `policyType` filter -- the API supports `SecurityPolicyFilterField` with `policyType` and `name` filters; CLI doesn't use them
- [ ] `securityPolicy` query supports lookup by `name` (not just `id`). CLI only looks up by ID.

### 3h. Remote Networks

- [ ] `location` field -- the API type includes it; verify it's fetched on list/show
- [ ] `gateways` edge -- not included in list/show queries

---

## 4. DNS Filtering -- Stale / Broken Implementation

The CLI's `dnssec.py` module uses mutations that are NOT in the current API reference, and the show query is missing required parameters.

### 4a. Deprecated Mutations

- [ ] `dnsFilteringAllowedDomainsSet` -- NOT in current API. Replace with `dnsFilteringProfileUpdate(id, allowedDomains)`
- [ ] `dnsFilteringDeniedDomainsSet` -- NOT in current API. Replace with `dnsFilteringProfileUpdate(id, deniedDomains)`

### 4b. Show Query Missing `id` Parameter

- [ ] `SHOW_DNS_PROFILE` calls `dnsFilteringProfile` without an `id` argument. The API requires `id: ID!`. This query will fail unless the server has special handling for parameterless calls.

### 4c. Missing DNS Filtering Operations

- [ ] `dnsFilteringProfiles` query -- list all profiles (returns DnsFilteringProfileMetadata[])
- [ ] `dnsFilteringProfileCreate` mutation -- create a new profile
- [ ] `dnsFilteringProfileDelete` mutation -- delete a profile
- [ ] `dnsFilteringProfileUpdate` mutation -- the full update includes:
  - `name`, `priority`, `fallbackMethod` (AUTO/STRICT)
  - `groups` -- assign groups to the profile
  - `contentCategoryConfig` -- block gambling, dating, adult content, social media, games, streaming, piracy
  - `securityCategoryConfig` -- threat intel feeds, Google Safe Browsing, cryptojacking, IDN homographs, typosquatting, DNS rebinding, newly registered domains
  - `privacyCategoryConfig` -- affiliate/tracking, disguised trackers, ads & trackers

---

## 5. Deprecated / Stale Patterns in CLI

### 5a. Deprecated Fields Still Used

- [ ] `usageBasedAutolockDurationDays` on Resources -- deprecated in favor of `accessPolicy { mode, durationSeconds }`
- [ ] `groups` and `serviceAccounts` edges on Resource -- deprecated in favor of unified `access` connection
- [ ] `isAdmin` on User -- deprecated in favor of `role`
- [ ] `kandji` on DevicePosture -- deprecated in favor of `iru`

### 5b. Query Naming Inconsistencies

- [ ] Multiple queries use the operation name `listGroup` for non-group entities (resources, users, devices, networks)
- [ ] `DELETE_ACCOUNT` and other mutations use the operation name `ObjCreate` (copy-paste artifact)
- [ ] `LIST_ACCOUNTS` query is anonymous (no operation name)

---

## 6. New API Features Not Yet Leveraged

### 6a. Tags System

- [ ] Resources (all types) support `tags: [Tag!]!` (key-value pairs)
- [ ] `Taggable` interface implemented by NetworkResource, KubernetesResource, SSHResource, WebAppResource
- [ ] `resourceCreate` and `resourceUpdate` accept `tags: [TagInput!]`
- [ ] Add CLI commands: `resource tag add`, `resource tag remove`, `resource tag list`

### 6b. Access Policy Model (replaces autolock)

- [ ] `AccessPolicy { mode: AccessMode!, durationSeconds: Int }` -- mode is MANUAL, AUTO_LOCK, or ACCESS_REQUEST
- [ ] `AccessPolicyInput` accepted on create/update for all resource types
- [ ] CLI should migrate from `usageBasedAutolockDurationDays` to `accessPolicy`

### 6c. Approval Workflow

- [ ] `approvalMode` field (MANUAL, AUTOMATIC) on resources
- [ ] `approverGroups` edge on resources
- [ ] `addedApproverGroupIds` / `removedApproverGroupIds` / `approverGroupIds` on resourceUpdate
- [ ] CLI has basic autolock/autoapprove commands but doesn't expose approver group management

### 6d. Events / OIDC

- [ ] `eventsSyncOidcProviderUrl` query -- returns the OIDC Identity Provider URL for the current tenant. Could be useful as a utility command.

### 6e. Remote Network Types

- [ ] `RemoteNetworkType` enum: REGULAR, EXIT -- the CLI doesn't differentiate or filter by network type

### 6f. Connector Filters

- [ ] `ConnectorFilterInput` -- filter connectors on list queries (not currently used)

### 6g. Resource Access with Security Policy Override

- [ ] `AccessInput` includes `principalId`, `principalType` (GROUP/SERVICE_ACCOUNT), and optional `securityPolicyId` for per-edge policy override
- [ ] The CLI's `resourceAccessAdd`/`resourceAccessSet` may not expose the per-edge security policy option

---

## 7. Priority Recommendations

### Critical (broken functionality)
1. Fix `dnssec.py` -- uses deprecated mutations and missing `id` param on show
2. Add `deviceUnarchive` -- asymmetric: archive exists but unarchive doesn't
3. Add `connectorDelete` -- only entity with create but no delete

### High (missing entity types that customers use)
4. Implement Gateway CRUD -- required for SSH/K8s/WebApp resources
5. Implement Certificate Authority management -- prerequisite for Gateways
6. Implement Access Request workflows -- approve/reject from CLI
7. Implement SSH/Kubernetes/WebApp resource types -- full typed resource support

### Medium (missing operations on existing entities)
8. Add `securityPolicyUpdate` -- currently read-only
9. Add group rename, activate/deactivate
10. Add service account rename
11. Add resource rename, protocol update, browser shortcut toggle
12. Add user first/last name update
13. Add remote network lookup by name
14. Add tags management for resources

### Low (field coverage, deprecation cleanup)
15. Migrate from deprecated fields (usageBasedAutolockDurationDays, groups/serviceAccounts edges, kandji)
16. Add missing fields to queries (User.type, Group.originId, Group.securityPolicy, RemoteNetwork.gateways, etc.)
17. Fix query operation name inconsistencies
18. Add filter support to list commands (connectors, devices, service accounts)
