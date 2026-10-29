# Service Tenancy (dev build)

Onboards a tenant namespace onto a Platform namespace. Lab prototype for the Service Tenancy design, not for production. Needs the dev Services build v7.0.1-xns2.

Create a `Tenant` in the Platform namespace (the one that holds the TopoNodes and Interfaces):

```yaml
apiVersion: tenancy.dtrichards01.github.io/v1alpha1
kind: Tenant
metadata:
  name: pan
  namespace: clab-srl-leaf-spine-dcgw
spec:
  tenantNamespace: clab-pan-d3l
  interfaces:
    - interface: srl-leaf-1-ethernet-1-6
      untagged: true
  ranges:
    evi: {start: 10000, size: 1000}
    vni: {start: 1010000, size: 1000}
    tunnelIndex: {start: 10000, size: 1000}
```

In the same transaction, create `tenancy-evi-pool`, `tenancy-vni-pool` and `tenancy-tunnel-index-pool` (IndexAllocationPool) in the tenant namespace with those ranges. EDA 26.8.1 does not let app intents create pools, so the Platform does; the Tenant rejects pools outside its ranges. Tenant BridgeDomains that attach to Platform Interfaces must allocate from those pools.

The dev Services build then lets a tenant BridgeInterface set `interfaceNamespace` to the Platform namespace only for granted Interfaces and VLANs, with EVI, VNI and tunnel index inside the tenant ranges. Explicit route targets are rejected.

Not covered: routed (IRB/Router) services, tenant roles, mac-vrf name clashes between namespaces.
