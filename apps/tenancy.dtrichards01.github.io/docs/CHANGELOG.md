# Changelog

## v0.1.1

- No longer creates the tenant range pools: EDA 26.8.1 denies app intents writes to IndexAllocationPool. The Platform creates them; the Tenant checks they stay inside the ranges.

## v0.1.0

- `Tenant`: interface grants (name or label selector, untagged and VLANs) and EVI/VNI/tunnel index ranges.
- Creates the tenant range pools in the tenant namespace.
- Rejects overlaps with the Platform pools and other tenants.
