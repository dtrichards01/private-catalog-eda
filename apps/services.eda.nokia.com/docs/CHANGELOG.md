# Changelog

## v7.0.1-xns2

- Cross-namespace use needs a Tenant (tenancy.dtrichards01.github.io) in the Platform namespace: the Interface and VLANs must be granted, EVI/VNI/tunnel index must be inside the tenant ranges, and explicit route targets are rejected.

## v7.0.1-xns1

- BridgeInterface `spec.interfaceNamespace` (also in VirtualNetwork bridgeInterfaces).
- BridgeDomainDeployment `spec.nodeNamespace`.
- Node config for those resources is written to the Interface namespace.
