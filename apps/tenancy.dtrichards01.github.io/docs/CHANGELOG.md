# Changelog

## v0.2.2

- Tenant status shows the resolved grants: `numInterfaces`, a one-line `grantedInterfaces` summary and the `interfaces` list, after label selectors are applied. The Tenants table shows the count and summary, so a selector grant no longer looks out of step with the tenant's Granted Interfaces.
- New internal `TenantState` (not exposed) and a state intent that writes the Tenant status, following the Services app pattern.
- Granted Interface description explains it is the tenant's read-only, per-Interface view.

## v0.2.1

- UI: Tenant and Granted Interface tables list name and namespace. Without `.metadata.name` in the default columns the table did not load the name, and Edit requested `tenants/undefined` and showed "Resource not found".

## v0.2.0

- `GrantedInterface` (read-only): one per granted Interface, written into the tenant namespace with node, port, untagged and VLANs. Label-selector grants are resolved to Interface names.

## v0.1.1

- No longer creates the tenant range pools: EDA 26.8.1 denies app intents writes to IndexAllocationPool. The Platform creates them; the Tenant checks they stay inside the ranges.

## v0.1.0

- `Tenant`: interface grants (name or label selector, untagged and VLANs) and EVI/VNI/tunnel index ranges.
- Creates the tenant range pools in the tenant namespace.
- Rejects overlaps with the Platform pools and other tenants.
