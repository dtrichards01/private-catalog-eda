# Changelog

## v1.0.1

- Firewall interfaces commit even when the leaf attachment cannot be emitted
- List columns for the firewall and its NICs

## v1.0.0

- External firewall endpoints for Palo Alto and FortiGate
- Health, status, and interface changes use the vendor API
- Intents validate the CR directly. They do not import generated `pysrc` modules.
