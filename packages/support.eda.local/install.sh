#!/usr/bin/env bash
# Install EDA Support Automation from private-eda-catalog.
set -euo pipefail

APP_GROUP="support.eda.local"
APP_VERSION="v1alpha1"
CATALOG_REPO="${CATALOG_REPO:-https://github.com/dtrichards01/private-catalog-eda.git}"
NAMESPACE="${NAMESPACE:-eda}"

echo "==> EDA Support App install helper"
echo "    Catalog: ${CATALOG_REPO}"
echo "    App: ${APP_GROUP}/${APP_VERSION}"
echo

cat <<'EOF'
Recommended: install via EDA App Management UI
----------------------------------------------
1. Push this repo to GitHub (private-catalog-eda).
2. In EDA UI: Administration -> App Management -> Catalogs -> Add catalog
   - URL: https://github.com/dtrichards01/private-catalog-eda.git
   - Branch: main
3. Install app "EDA Support Automation" (support.eda.local v1alpha1).
4. Build and push the operator image (once per release):
     docker build -t ghcr.io/dtrichards01/private-eda-registry/support:v1.0.0 packages/support.eda.local
     docker push ghcr.io/dtrichards01/private-eda-registry/support:v1.0.0
5. Apply example CRs (optional):
     kubectl apply -f packages/support.eda.local/support/config/examples/

EOF

if command -v edactl >/dev/null 2>&1; then
  echo "==> edactl detected — attempting catalog app install"
  edactl app install \
    --catalog "${CATALOG_REPO}" \
    --group "${APP_GROUP}" \
    --version "${APP_VERSION}" \
    --namespace "${NAMESPACE}" || true
else
  echo "edactl not found — use App Management UI or kubectl apply on exported manifests."
fi

if command -v kubectl >/dev/null 2>&1; then
  echo
  echo "==> Applying example AlarmWorkflowRule + SupportMonitor (namespace=${NAMESPACE})"
  kubectl apply -n "${NAMESPACE}" -f "$(dirname "$0")/support/config/examples/" || true
fi

echo "Done."
