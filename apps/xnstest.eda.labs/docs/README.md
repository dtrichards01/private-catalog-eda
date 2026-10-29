# Cross Namespace Test

Throwaway probe for the Service Tenancy design. A `CrossNsProbe` in one namespace
reads a resource, emits a `CrossNsResult`, and optionally emits a `BridgeInterface`
in `spec.targetNamespace`. Uninstall after the test.
