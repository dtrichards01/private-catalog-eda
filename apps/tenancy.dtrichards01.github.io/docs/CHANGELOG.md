# Changelog

## v0.1.0

- `Tenant`: interface grants (name or label selector, untagged and VLANs) and EVI/VNI/tunnel index ranges.
- Creates the tenant range pools in the tenant namespace.
- Rejects overlaps with the Platform pools and other tenants.
