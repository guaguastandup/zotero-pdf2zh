#!/bin/sh
# Run on the Docker host, beside docker-compose.yaml. No interactive stdin.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mode=${1:-server}
case "$mode" in
  server|all) ;;
  *) echo 'Usage: sh update.sh [server|all]' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then echo 'Too many arguments' >&2; exit 2; fi
compose() {
  if [ "$compose_v2" = yes ]; then docker compose "$@"; else docker-compose "$@"; fi
}
if docker compose version >/dev/null 2>&1; then compose_v2=yes
elif command -v docker-compose >/dev/null 2>&1; then compose_v2=no
else echo 'Docker Compose is required.' >&2; exit 1; fi
compose config --quiet
echo 'Wait for active translations to finish before updating. Building the new Server image...'
compose build --pull --no-cache pdf2zh-server
if [ "$mode" = all ]; then
  # Resolve the image from Compose environment, including .env/overrides.
  compose run --rm -T --no-deps --entrypoint sh pdf2zh-server -c \
    'exec docker pull "${ZOTERO_PDF2ZH_FROM_IMAGE:-awwaawwa/pdfmathtranslate-next:latest}"'
fi
# No down, volume deletion or prune. Failed build/pull never reaches this step.
compose up -d --no-deps --no-build pdf2zh-server
compose ps pdf2zh-server
echo 'Update command completed. Check readiness with: docker compose logs --tail=50 pdf2zh-server'
