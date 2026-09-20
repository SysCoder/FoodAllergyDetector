#!/bin/bash
# Assemble a self-contained DigitalOcean Functions package and deploy it.
#
# `doctl serverless deploy <dir>` uploads only that directory, so the function
# cannot reference application modules living at the repository root. This
# stages a copy with the app files placed next to the handler, leaving the repo
# itself free of duplicated source.
#
# Usage:  scripts/stage_functions.sh [--deploy]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="${ROOT}/.stage/functions"
FN="${STAGE}/packages/app/http"

rm -rf "${ROOT}/.stage"
mkdir -p "${FN}/static"

cp "${ROOT}/functions/project.yml" "${STAGE}/project.yml"
cp "${ROOT}/functions/packages/app/http/__main__.py"      "${FN}/"
cp "${ROOT}/functions/packages/app/http/requirements.txt" "${FN}/"
cp "${ROOT}/functions/packages/app/http/build.sh"         "${FN}/"
chmod a+x "${FN}/build.sh"

# The application itself, unchanged.
for f in main.py allergens.py sources.py ingredients.py fallback.py vocabulary.json; do
  cp "${ROOT}/${f}" "${FN}/"
done
cp "${ROOT}/static/index.html" "${FN}/static/"

echo "staged -> ${STAGE}"
find "${STAGE}" -type f | sed "s|${STAGE}|  .|" | sort

if [[ "${1:-}" == "--deploy" ]]; then
  # project.yml declares TYPESAFE_API_KEY as ${TYPESAFE_API_KEY}, which doctl
  # resolves from the environment at deploy time. Fall back to .env so the
  # deploy does not depend on the caller having exported it by hand.
  if [[ -z "${TYPESAFE_API_KEY:-}" ]]; then
    if [[ -f "${ROOT}/.env" ]]; then
      TYPESAFE_API_KEY="$(grep -m1 '^TYPESAFE_API_KEY=' "${ROOT}/.env" | cut -d= -f2-)"
      export TYPESAFE_API_KEY
      echo "using TYPESAFE_API_KEY from .env (${#TYPESAFE_API_KEY} chars)"
    fi
  else
    echo "using TYPESAFE_API_KEY from the environment (${#TYPESAFE_API_KEY} chars)"
  fi

  if [[ -z "${TYPESAFE_API_KEY:-}" ]]; then
    echo "error: TYPESAFE_API_KEY is not set and no .env was found." >&2
    echo "       export it, or create .env with TYPESAFE_API_KEY=..." >&2
    exit 1
  fi

  echo
  echo "deploying (remote build: compiled wheels must be built for Linux)…"
  doctl serverless deploy "${STAGE}" --remote-build
fi
