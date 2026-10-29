# Changelog

## v0.2.0

- `GrantedInterface` (read-only): one per granted Interface, written into the tenant namespace with node, port, untagged and VLANs. Label-selector grants are resolved to Interface names.

## v0.1.1

- No longer creates the tenant range pools: EDA 26.8.1 denies app intents writes to IndexAllocationPool. The Platform creates them; the Tenant checks they stay inside the ranges.

## v0.1.0

- `Tenant`: interface grants (name or label selector, untagged and VLANs) and EVI/VNI/tunnel index ranges.
- Creates the tenant range pools in the tenant namespace.
- Rejects overlaps with the Platform pools and other tenants.
