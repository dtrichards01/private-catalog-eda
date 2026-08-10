# private-catalog-eda

Private EDA App Catalog for custom applications.

## Catalog layout

EDA Store discovers installable apps from:

- apps/<group>/manifest.yaml - catalog listing metadata
- Git tag apps/<group>/v<version> - registers a version in the Store (required)

Example: apps/banners.eda.local/manifest.yaml + tag apps/banners.eda.local/v1.0.0.

## Packages

Source packages for building app container images:

- packages/support.eda.local - EDA Support Automation app (alarms to workflows)
