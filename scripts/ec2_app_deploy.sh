#!/usr/bin/env bash
# Deploy relocation-jobs panel to EC2 (same host as Postgres + Redis).
#
# Usage:
#   ./scripts/ec2_app_deploy.sh check [--local]   # plan only: hashes, would rebuild/skip, no writes
#   ./scripts/ec2_app_deploy.sh sync              # rsync repo to EC2
#   ./scripts/ec2_app_deploy.sh sync --dry-run    # rsync -n (no remote writes)
#   ./scripts/ec2_app_deploy.sh deploy            # sync + build (if needed) + run
#   ./scripts/ec2_app_deploy.sh deploy --force    # rebuild images even if hashes match
#   ./scripts/ec2_app_deploy.sh deploy --dry-run  # same plan as check (no rsync/build/run)
#   ./scripts/ec2_app_deploy.sh prune             # dangling images + trim BuildKit cache
#   ./scripts/ec2_app_deploy.sh open-sg           # open HTTP/HTTPS on security group (manual)
#   ./scripts/ec2_app_deploy.sh status            # doctor: containers, disk/RAM, health, verdict
#   ./scripts/ec2_app_deploy.sh logs [svc] [N] [-f]  # panel|caddy|mcp|worker|playwright-worker|propagator|alloy|all
#   ./scripts/ec2_app_deploy.sh worker-logs       # tail fetch scheduler logs (alias)
#   ./scripts/ec2_app_deploy.sh image-sizes       # docker image sizes on EC2
#
# Requires: aws-postgres.env, SSH key at ~/Downloads/relocation.pem
# Optional Grafana Cloud (Alloy): GRAFANA_CLOUD_PROMETHEUS_URL, GRAFANA_CLOUD_PROMETHEUS_USER,
# GRAFANA_CLOUD_API_TOKEN in .env. Logs: GRAFANA_CLOUD_LOKI_URL, GRAFANA_CLOUD_LOKI_USER
# (token needs logs:write). See docs/operations/monitoring.md
# Disk: root fills from leftover panel/worker images; deploy prunes dangling
# images only. BuildKit cache is kept across deploys so tectonic/pip/playwright
# layers are reused — never wiped mid/post-deploy (use `prune` for that).
# This script never runs docker volume prune / system prune --volumes, and never
# stops or removes container pg or volume pgdata.
#
# Escape hatches:
#   FORCE_REBUILD=1   — same as deploy --force
#   FORCE_FRONTEND=1  — rebuild frontend even if source hash matches
#   FORCE_HOMEPAGE=1  — rebuild homepage even if source hash matches
#   DEPLOY_PLAYWRIGHT_WORKER=1 — build/run Chromium sidecar when
#     Dockerfile.ec2-worker-playwright exists (PR #6 light-worker split)
#
# Push-to-deploy is not wired. See docs/operations/ec2-deploy.md.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$ROOT/aws-postgres.env"
REMOTE_DIR=/home/ec2-user/relocation-jobs
HASH_FILE=.deploy-hashes
REGION="${AWS_REGION:-eu-central-1}"
EC2_SSH_USER="${EC2_SSH_USER:-ec2-user}"
EC2_SSH_KEY="${EC2_SSH_KEY:-$HOME/Downloads/relocation.pem}"
PANEL_IMAGE=relocation-panel:ec2
PANEL_CONTAINER=relocation-panel
MCP_CONTAINER=relocation-mcp
WORKER_IMAGE=relocation-fetch-worker:ec2
WORKER_CONTAINER=relocation-fetch-worker
PLAYWRIGHT_WORKER_IMAGE=relocation-fetch-worker:playwright
PLAYWRIGHT_WORKER_CONTAINER=relocation-playwright-worker
PLAYWRIGHT_WORKER_DOCKERFILE=Dockerfile.ec2-worker-playwright
DEPLOY_PLAYWRIGHT_WORKER="${DEPLOY_PLAYWRIGHT_WORKER:-0}"
PROPAGATOR_IMAGE=relocation-role-propagator:ec2
PROPAGATOR_CONTAINER=relocation-role-propagator
CADDY_CONTAINER=relocation-caddy
ALLOY_CONTAINER=relocation-alloy
ALLOY_IMAGE="${ALLOY_IMAGE:-grafana/alloy:v1.8.3}"
PANEL_PORT=10000
MCP_PORT=10001
MCP_PUBLIC_BASE_URL="${MCP_PUBLIC_BASE_URL:-https://mcp.kuchup.com}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
DRY_RUN="${DRY_RUN:-0}"
LOCAL_ONLY="${LOCAL_ONLY:-0}"
LOG_SERVICE=all
LOG_FOLLOW=0
FRONTEND_ACTION=skipped
HOMEPAGE_ACTION=skipped
PANEL_ACTION=skipped
WORKER_ACTION=skipped
PLAYWRIGHT_ACTION=skipped
PROPAGATOR_ACTION=skipped

PROTECTED_CONTAINERS='pg postgres relocation-redis'
PROTECTED_VOLUMES='pgdata'

log() { printf '[ec2-app] %s\n' "$*"; }
die() { printf '[ec2-app] ERROR: %s\n' "$*" >&2; exit 1; }
q() { printf '%q' "$1"; }

phase() {
  local name="$1"
  shift
  local t0=$SECONDS
  log "phase start: ${name}"
  "$@"
  log "phase done:  ${name} ($((SECONDS - t0))s)"
}

assert_unprotected_name() {
  local name="$1"
  local item
  for item in $PROTECTED_CONTAINERS $PROTECTED_VOLUMES; do
    if [[ "$name" == "$item" ]]; then
      die "refusing to modify protected Docker object: ${name}"
    fi
  done
}

load_state() {
  [[ -f "$STATE_FILE" ]] || die "Missing $STATE_FILE"
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  [[ -n "${ELASTIC_IP:-}" ]] || die "ELASTIC_IP missing in $STATE_FILE"
  [[ -n "${DB_PASSWORD:-}" ]] || die "DB_PASSWORD missing in $STATE_FILE"
}

ssh_cmd() {
  local key_args=()
  [[ -f "$EC2_SSH_KEY" ]] && key_args=(-i "$EC2_SSH_KEY")
  ssh "${key_args[@]}" -o StrictHostKeyChecking=accept-new "${EC2_SSH_USER}@${ELASTIC_IP}" "$@"
}

rsync_cmd() {
  local key_args=() extra_args=()
  [[ -f "$EC2_SSH_KEY" ]] && key_args=(-e "ssh -i ${EC2_SSH_KEY} -o StrictHostKeyChecking=accept-new")
  extra_args=("$@")
  rsync -az --delete \
    "${extra_args[@]}" \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude 'node_modules/' \
    --exclude 'frontend/node_modules/' \
    --exclude 'homepage/node_modules/' \
    --exclude 'homepage/.next/' \
    --exclude 'homepage/out/' \
    --exclude '.entire/' \
    --exclude 'data/' \
    --exclude '/dist/' \
    --exclude '__pycache__/' \
    --exclude '.env' \
    --exclude 'aws-postgres.env' \
    --exclude '.pytest_cache/' \
    --exclude '*.pyc' \
    --exclude '.deploy-hashes' \
    --exclude '.source-hash' \
    "${key_args[@]}" \
    "$ROOT/" "${EC2_SSH_USER}@${ELASTIC_IP}:${REMOTE_DIR}/"
}

redis_password() {
  if [[ -n "${REDIS_PASSWORD:-}" ]]; then
    printf '%s' "$REDIS_PASSWORD"
    return
  fi
  if [[ -f "$ROOT/.env" ]]; then
    local url
    url="$(grep -E '^REDIS_URL=' "$ROOT/.env" | cut -d= -f2- || true)"
    if [[ "$url" =~ redis://:([^@]+)@ ]]; then
      printf '%s' "${BASH_REMATCH[1]}"
      return
    fi
  fi
  die "Set REDIS_PASSWORD or REDIS_URL in .env"
}

panel_secret() {
  if [[ -f "$ROOT/.env" ]]; then
    local key
    key="$(grep -E '^PANEL_SECRET_KEY=' "$ROOT/.env" | cut -d= -f2- || true)"
    if [[ -n "$key" && "$key" != "change-me-to-a-long-random-string" ]]; then
      printf '%s' "$key"
      return
    fi
  fi
  openssl rand -hex 32
}

admin_emails() {
  if [[ -f "$ROOT/.env" ]]; then
    local emails
    emails="$(grep -E '^PANEL_ADMIN_EMAILS=' "$ROOT/.env" | cut -d= -f2- || true)"
    if [[ -n "$emails" ]]; then
      printf '%s' "$emails"
      return
    fi
  fi
  printf '%s' "${PANEL_ADMIN_EMAILS:-}"
}

google_client_id() {
  printf '%s' "${GOOGLE_CLIENT_ID:-$(_dotenv_value GOOGLE_CLIENT_ID)}"
}

google_client_secret() {
  printf '%s' "${GOOGLE_CLIENT_SECRET:-$(_dotenv_value GOOGLE_CLIENT_SECRET)}"
}

google_redirect_uri() {
  printf '%s' "${GOOGLE_REDIRECT_URI:-$(_dotenv_value GOOGLE_REDIRECT_URI)}"
}

nowpayments_api_key() {
  printf '%s' "${NOWPAYMENTS_API_KEY:-$(_dotenv_value NOWPAYMENTS_API_KEY)}"
}

nowpayments_ipn_secret() {
  printf '%s' "${NOWPAYMENTS_IPN_SECRET:-$(_dotenv_value NOWPAYMENTS_IPN_SECRET)}"
}

nowpayments_sandbox() {
  local value
  value="${NOWPAYMENTS_SANDBOX:-$(_dotenv_value NOWPAYMENTS_SANDBOX)}"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes) printf '1' ;;
    *) printf '' ;;
  esac
}

panel_allow_register() {
  local value
  value="${PANEL_ALLOW_REGISTER:-$(_dotenv_value PANEL_ALLOW_REGISTER)}"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    1|true|yes) printf '1' ;;
    *) printf '0' ;;
  esac
}

panel_public_base_url() {
  local value
  value="${PANEL_PUBLIC_BASE_URL:-$(_dotenv_value PANEL_PUBLIC_BASE_URL)}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value"
    return
  fi
  printf '%s' "https://kuchup.com"
}

_dotenv_value() {
  local key="$1"
  [[ -f "$ROOT/.env" ]] || return 0
  grep -E "^${key}=" "$ROOT/.env" 2>/dev/null | cut -d= -f2- || true
}

sqs_queue_url() {
  printf '%s' "${SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL:-$(_dotenv_value SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL)}"
}

aws_access_key() {
  printf '%s' "${AWS_ACCESS_KEY_ID:-$(_dotenv_value AWS_ACCESS_KEY_ID)}"
}

aws_secret_key() {
  printf '%s' "${AWS_SECRET_ACCESS_KEY:-$(_dotenv_value AWS_SECRET_ACCESS_KEY)}"
}

aws_region_name() {
  local value
  value="${AWS_REGION:-$(_dotenv_value AWS_REGION)}"
  printf '%s' "${value:-eu-central-1}"
}

grafana_cloud_configured() {
  local url user token
  url="${GRAFANA_CLOUD_PROMETHEUS_URL:-$(_dotenv_value GRAFANA_CLOUD_PROMETHEUS_URL)}"
  user="${GRAFANA_CLOUD_PROMETHEUS_USER:-$(_dotenv_value GRAFANA_CLOUD_PROMETHEUS_USER)}"
  token="${GRAFANA_CLOUD_API_TOKEN:-$(_dotenv_value GRAFANA_CLOUD_API_TOKEN)}"
  [[ -n "$url" && -n "$user" && -n "$token" ]]
}

grafana_cloud_url() {
  printf '%s' "${GRAFANA_CLOUD_PROMETHEUS_URL:-$(_dotenv_value GRAFANA_CLOUD_PROMETHEUS_URL)}"
}

grafana_cloud_user() {
  printf '%s' "${GRAFANA_CLOUD_PROMETHEUS_USER:-$(_dotenv_value GRAFANA_CLOUD_PROMETHEUS_USER)}"
}

grafana_cloud_token() {
  printf '%s' "${GRAFANA_CLOUD_API_TOKEN:-$(_dotenv_value GRAFANA_CLOUD_API_TOKEN)}"
}

grafana_cloud_loki_url() {
  printf '%s' "${GRAFANA_CLOUD_LOKI_URL:-$(_dotenv_value GRAFANA_CLOUD_LOKI_URL)}"
}

grafana_cloud_loki_user() {
  printf '%s' "${GRAFANA_CLOUD_LOKI_USER:-$(_dotenv_value GRAFANA_CLOUD_LOKI_USER)}"
}

grafana_cloud_loki_configured() {
  local url user
  url="$(grafana_cloud_loki_url)"
  user="$(grafana_cloud_loki_user)"
  [[ -n "$url" && -n "$user" ]]
}

container_for_log_service() {
  case "$1" in
    panel) printf '%s' "$PANEL_CONTAINER" ;;
    caddy) printf '%s' "$CADDY_CONTAINER" ;;
    mcp) printf '%s' "$MCP_CONTAINER" ;;
    worker) printf '%s' "$WORKER_CONTAINER" ;;
    playwright-worker|pw-worker) printf '%s' "$PLAYWRIGHT_WORKER_CONTAINER" ;;
    propagator) printf '%s' "$PROPAGATOR_CONTAINER" ;;
    alloy) printf '%s' "$ALLOY_CONTAINER" ;;
    pg) printf '%s' "pg" ;;
    redis) printf '%s' "relocation-redis" ;;
    all) printf '%s' "" ;;
    *) return 1 ;;
  esac
}

# Content hash of a source tree (or extra files). Replaces find -newer | grep,
# which under `set -o pipefail` can SIGPIPE and skip a needed rebuild.
_content_hash() {
  (
    cd "$ROOT"
    {
      for src in "$@"; do
        if [[ -d "$src" ]]; then
          find "$src" \
            \( -name node_modules -o -name .next -o -name out -o -name __pycache__ \) -prune \
            -o -type f -print
        elif [[ -f "$src" ]]; then
          printf '%s\n' "$src"
        fi
      done
    } | LC_ALL=C sort -u | while IFS= read -r path; do
      [[ -e "$path" ]] || continue
      printf '%s\0' "$path"
      cat "$path"
    done | sha256sum | awk '{print $1}'
  )
}

_stamp_matches() {
  local stamp="$1"
  local digest="$2"
  [[ -f "$stamp" ]] || return 1
  [[ "$(tr -d '[:space:]' <"$stamp")" == "$digest" ]]
}

maybe_build_frontend() {
  [[ -d "$ROOT/frontend" ]] || return 0
  local out="$ROOT/relocation_jobs/static/dist/board.js"
  local stamp="$ROOT/relocation_jobs/static/dist/.source-hash"
  local digest
  digest="$(_content_hash frontend)"
  local need=0
  if [[ "${FORCE_FRONTEND:-0}" == "1" ]]; then
    need=1
  elif [[ ! -f "$out" ]]; then
    need=1
  elif ! _stamp_matches "$stamp" "$digest"; then
    need=1
  fi
  if [[ "$need" -eq 0 ]]; then
    FRONTEND_ACTION=skipped
    log "Frontend up to date (${digest:0:12}…) — skipping npm build"
    return 0
  fi
  FRONTEND_ACTION=rebuilt
  if [[ "$DRY_RUN" == "1" ]]; then
    FRONTEND_ACTION=would-rebuild
    log "dry-run: would build frontend (board.js) hash=${digest:0:12}…"
    return 0
  fi
  log "Building frontend (board.js)..."
  (cd "$ROOT/frontend" && npm run build --silent)
  printf '%s\n' "$digest" >"$stamp"
}

maybe_build_homepage() {
  [[ -d "$ROOT/homepage" ]] || return 0
  local out="$ROOT/relocation_jobs/static/homepage/index.html"
  local stamp="$ROOT/relocation_jobs/static/homepage/.source-hash"
  local digest
  digest="$(_content_hash homepage scripts/export_homepage_countries.py scripts/export_homepage_country_snapshots.py)"
  local need=0
  if [[ "${FORCE_HOMEPAGE:-0}" == "1" ]]; then
    need=1
  elif [[ ! -f "$out" ]]; then
    need=1
  elif ! _stamp_matches "$stamp" "$digest"; then
    need=1
  fi
  if [[ "$need" -eq 0 ]]; then
    HOMEPAGE_ACTION=skipped
    log "Homepage up to date (${digest:0:12}…) — skipping static export"
    return 0
  fi
  HOMEPAGE_ACTION=rebuilt
  if [[ "$DRY_RUN" == "1" ]]; then
    HOMEPAGE_ACTION=would-rebuild
    log "dry-run: would build homepage (static export) hash=${digest:0:12}…"
    return 0
  fi
  log "Building homepage (static export)..."
  "$ROOT/scripts/build_homepage.sh"
  printf '%s\n' "$digest" >"$stamp"
}

cmd_sync() {
  load_state
  maybe_build_frontend
  maybe_build_homepage
  log "Syncing to ${EC2_SSH_USER}@${ELASTIC_IP}:${REMOTE_DIR}"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "dry-run rsync (no remote writes)"
    rsync_cmd -n --info=stats2 | tail -n 20
    log "dry-run sync plan OK"
    return 0
  fi
  ssh_cmd "mkdir -p ${REMOTE_DIR}"
  rsync_cmd
  log "Sync OK"
}

cmd_open_sg() {
  load_state
  command -v aws >/dev/null 2>&1 || die "aws CLI required"
  local sg="${SECURITY_GROUP_ID:-}"
  if [[ -z "$sg" && -n "${EC2_INSTANCE_ID:-}" ]]; then
    sg="$(aws ec2 describe-instances --region "$REGION" --instance-ids "$EC2_INSTANCE_ID" \
      --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)"
  fi
  [[ -n "$sg" ]] || die "Could not resolve security group"
  for port in 80 443; do
    aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$sg" \
      --ip-permissions "IpProtocol=tcp,FromPort=${port},ToPort=${port},IpRanges=[{CidrIp=0.0.0.0/0,Description=panel-http}]" \
      2>/dev/null || log "Port ${port} may already be open"
  done
  log "Security group ${sg}: TCP 80/443 open"
}

# Docker disk reclaim — NEVER touch volumes or the Postgres/Redis containers.
#
# Data lives in named volumes (`pgdata`, redis data), not in images. Safe ops:
#   docker image prune -f     # dangling (<none>) images only
#   docker builder prune -af  # build cache only (manual prune)
# Forbidden in this script (would risk DB wipe):
#   docker volume prune / docker volume rm
#   docker system prune --volumes
#   docker rm -v pg
#   any prune that stops or removes container `pg`
#
# Deploy never wipes BuildKit cache — that is what forces tectonic/pip/playwright
# re-downloads on every deploy. Manual `prune` may reclaim builder cache when
# disk is tight (keeps ~8G of recent cache so the next deploy is not cold).
remote_assert_db_safe() {
  local phase="${1:-check}"
  ssh_cmd bash -s -- "$phase" <<'SCRIPT'
set -euo pipefail
phase="${1:-check}"
if ! docker inspect -f '{{.State.Running}}' pg 2>/dev/null | grep -qx true; then
  echo "[ec2-app] ERROR: Postgres container 'pg' is not running (${phase}) — aborting" >&2
  exit 1
fi
if ! docker volume inspect pgdata >/dev/null 2>&1; then
  echo "[ec2-app] ERROR: Docker volume 'pgdata' missing (${phase}) — aborting" >&2
  exit 1
fi
printf '[ec2-app] db guard (%s): pg running, volume pgdata present\n' "$phase"
SCRIPT
}

remote_assert_disk() {
  local mode="${1:-abort}"
  local usep
  usep="$(ssh_cmd "df -P / | awk 'NR==2{gsub(/%/,\"\",\$5); print \$5}'" 2>/dev/null || echo 0)"
  if [[ "$usep" =~ ^[0-9]+$ ]] && (( usep >= 95 )); then
    if [[ "$mode" == "warn" ]]; then
      log "WARN: root disk ${usep}% used (>=95%)"
      return 0
    fi
    die "root disk ${usep}% used (>=95%) — aborting before builds; run prune or grow EBS"
  fi
  if [[ "$usep" =~ ^[0-9]+$ ]] && (( usep >= 85 )); then
    log "WARN: root disk ${usep}% used (>=85%)"
  fi
}

remote_docker_prune() {
  local builder="${1:-}"
  local label="${2:-}"
  [[ -n "$label" ]] && log "Docker prune (${label})..."
  if [[ "$DRY_RUN" == "1" ]]; then
    log "dry-run: skip docker image prune (${label})"
    return 0
  fi
  ssh_cmd bash -s -- "$builder" <<'SCRIPT'
set -euo pipefail
builder_arg="${1:-}"

assert_db_safe() {
  local phase="$1"
  if ! docker inspect -f '{{.State.Running}}' pg 2>/dev/null | grep -qx true; then
    echo "[ec2-app] ERROR: Postgres container 'pg' is not running (${phase}) — refusing prune" >&2
    exit 1
  fi
  if ! docker volume inspect pgdata >/dev/null 2>&1; then
    echo "[ec2-app] ERROR: Docker volume 'pgdata' missing (${phase}) — refusing prune" >&2
    exit 1
  fi
}

assert_db_safe "before prune"
printf '[ec2-app] disk before prune: '
df -h / | awk 'NR==2 {print $3 " used / " $2 " (" $5 ")"}'

# Dangling images only — never -a (unused), volumes, containers.
docker image prune -f
# Manual prune only: trim builder cache but keep recent layers warm.
if [ "$builder_arg" = "builder" ]; then
  docker builder prune -af --keep-storage 8GB >/dev/null
fi

assert_db_safe "after prune"
printf '[ec2-app] disk after prune:  '
df -h / | awk 'NR==2 {print $3 " used / " $2 " (" $5 ")"}'
printf '[ec2-app] db guard: pg running, volume pgdata present\n'
SCRIPT
}

cmd_prune() {
  load_state
  remote_docker_prune "builder" "manual"
}

# Compute a content hash of image inputs. Static assets are bind-mounted into
# the panel at runtime, so they are omitted — changing CSS/homepage alone should
# not force a Python image rebuild. .dockerignore is included so COPY . . scope
# changes invalidate the skip.
image_input_paths() {
  local kind="$1"
  case "$kind" in
    panel)
      printf '%s\n' Dockerfile.ec2 .dockerignore requirements.txt docker-entrypoint.sh
      [[ -f docker-entrypoint-mcp.sh ]] && printf '%s\n' docker-entrypoint-mcp.sh
      [[ -f scripts/mcp_http_server.py ]] && printf '%s\n' scripts/mcp_http_server.py
      [[ -f deploy/ec2/tectonic-warm.tex ]] && printf '%s\n' deploy/ec2/tectonic-warm.tex
      find relocation_jobs \
        \( -path 'relocation_jobs/static' -o -path 'relocation_jobs/static/*' \
           -o -name '__pycache__' -o -name '*.pyc' \) -prune \
        -o -type f -print
      ;;
    worker)
      printf '%s\n' Dockerfile.ec2-worker .dockerignore requirements.txt scripts/fetch_scheduler_worker.py
      [[ -f requirements-playwright.txt ]] && printf '%s\n' requirements-playwright.txt
      [[ -f apps/fetch-worker/run.py ]] && printf '%s\n' apps/fetch-worker/run.py
      find relocation_jobs \
        \( -path 'relocation_jobs/static' -o -path 'relocation_jobs/static/*' \
           -o -name '__pycache__' -o -name '*.pyc' \) -prune \
        -o -type f -print
      ;;
    playwright-worker)
      printf '%s\n' Dockerfile.ec2-worker-playwright .dockerignore requirements.txt
      [[ -f requirements-playwright.txt ]] && printf '%s\n' requirements-playwright.txt
      [[ -f apps/playwright-worker/run.py ]] && printf '%s\n' apps/playwright-worker/run.py
      find relocation_jobs \
        \( -path 'relocation_jobs/static' -o -path 'relocation_jobs/static/*' \
           -o -name '__pycache__' -o -name '*.pyc' \) -prune \
        -o -type f -print
      ;;
    propagator)
      printf '%s\n' go.mod go.sum
      find apps/role-propagator role_propagator -type f ! -name 'role-propagator' -print
      ;;
    *)
      echo "unknown hash kind: $kind" >&2
      return 1
      ;;
  esac
}

hash_input_paths() {
  image_input_paths "$1" | LC_ALL=C sort -u | while IFS= read -r path; do
    [[ -e "$path" ]] || continue
    printf '%s\0' "$path"
    cat "$path"
  done | sha256sum | awk '{print $1}'
}

local_image_hash() {
  (cd "$ROOT" && hash_input_paths "$1")
}

remote_image_hash() {
  local kind="$1"
  ssh_cmd bash -s -- "$REMOTE_DIR" "$kind" <<EOF
set -euo pipefail
cd "\$1"
kind="\$2"
$(declare -f image_input_paths hash_input_paths)
hash_input_paths "\$kind"
EOF
}

remote_saved_hash() {
  local kind="$1"
  ssh_cmd bash -s -- "$REMOTE_DIR" "$HASH_FILE" "$kind" <<'SCRIPT'
set -euo pipefail
cd "$1"
hash_file="$2"
kind="$3"
[[ -f "$hash_file" ]] || exit 0
awk -F= -v k="$kind" '$1 == k { print $2; exit }' "$hash_file"
SCRIPT
}

remote_save_hash() {
  local kind="$1"
  local digest="$2"
  [[ "$DRY_RUN" == "1" ]] && return 0
  ssh_cmd bash -s -- "$REMOTE_DIR" "$HASH_FILE" "$kind" "$digest" <<'SCRIPT'
set -euo pipefail
cd "$1"
hash_file="$2"
kind="$3"
digest="$4"
tmp="$(mktemp)"
if [[ -f "$hash_file" ]]; then
  grep -v "^${kind}=" "$hash_file" >"$tmp" || true
fi
printf '%s=%s\n' "$kind" "$digest" >>"$tmp"
mv "$tmp" "$hash_file"
SCRIPT
}

# Returns 0 if a docker build is needed. $3 is the precomputed input digest.
image_needs_rebuild() {
  local kind="$1"
  local image="$2"
  local current="$3"
  if [[ "$FORCE_REBUILD" == "1" ]]; then
    log "${kind}: FORCE_REBUILD — rebuilding"
    return 0
  fi
  if ! ssh_cmd "docker image inspect ${image} >/dev/null 2>&1"; then
    log "${kind}: image ${image} missing — rebuilding"
    return 0
  fi
  local saved
  saved="$(remote_saved_hash "$kind")"
  if [[ -n "$saved" && "$saved" == "$current" ]]; then
    log "${kind}: inputs unchanged (${current:0:12}…) — skipping docker build"
    return 1
  fi
  log "${kind}: inputs changed — rebuilding"
  return 0
}

build_remote_image() {
  local dockerfile="$1"
  local image="$2"
  log "Building ${image} on EC2 (-f ${dockerfile})..."
  ssh_cmd bash -s -- "$REMOTE_DIR" "$dockerfile" "$image" <<'SCRIPT'
set -euo pipefail
cd "$1"
dockerfile="$2"
image="$3"
cache_args=()
if docker image inspect "$image" >/dev/null 2>&1; then
  cache_args=(--cache-from "$image")
fi
DOCKER_BUILDKIT=1 docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  "${cache_args[@]}" \
  -f "$dockerfile" -t "$image" .
SCRIPT
}

maybe_rebuild_image() {
  local kind="$1" image="$2" dockerfile="$3" action_var="$4"
  local digest
  digest="$(remote_image_hash "$kind")"
  if image_needs_rebuild "$kind" "$image" "$digest"; then
    printf -v "$action_var" '%s' rebuilt
    if [[ "$DRY_RUN" == "1" ]]; then
      printf -v "$action_var" '%s' would-rebuild
      return 0
    fi
    build_remote_image "$dockerfile" "$image"
  else
    printf -v "$action_var" '%s' skipped
  fi
  remote_save_hash "$kind" "$digest"
}

preflight_local() {
  local fail=0
  [[ -f "$ROOT/Dockerfile.ec2" ]] || { log "MISSING Dockerfile.ec2"; fail=1; }
  [[ -f "$ROOT/Dockerfile.ec2-worker" ]] || { log "MISSING Dockerfile.ec2-worker"; fail=1; }
  if [[ -f "$ROOT/deploy/ec2/Caddyfile" ]]; then
    log "OK deploy/ec2/Caddyfile"
  else
    log "WARN deploy/ec2/Caddyfile missing (operator laptop / EC2 copy; see docs/operations/ec2-deploy.md)"
  fi
  if [[ -f "$ROOT/$PLAYWRIGHT_WORKER_DOCKERFILE" ]]; then
    log "OK ${PLAYWRIGHT_WORKER_DOCKERFILE} (Playwright sidecar available)"
  else
    log "Playwright sidecar Dockerfile not in this tree (open PR #6) — default worker unchanged"
  fi
  return "$fail"
}

preflight_deploy() {
  [[ -f "$EC2_SSH_KEY" ]] || die "SSH key missing: $EC2_SSH_KEY"
  preflight_local || die "local preflight failed"
  [[ -f "$ROOT/deploy/ec2/Caddyfile" ]] || die "missing deploy/ec2/Caddyfile (see docs/operations/ec2-deploy.md)"
  ssh_cmd "true" || die "SSH failed"
  remote_assert_db_safe "preflight"
  remote_assert_disk
  log "preflight OK — will not touch ${PROTECTED_CONTAINERS} / ${PROTECTED_VOLUMES}"
}

rm_app_container() {
  local name="$1"
  assert_unprotected_name "$name"
  ssh_cmd "docker rm -f ${name} 2>/dev/null || true" || true
}

playwright_sidecar_requested() {
  [[ "${DEPLOY_PLAYWRIGHT_WORKER}" == "1" ]]
}

playwright_sidecar_available() {
  [[ -f "$ROOT/$PLAYWRIGHT_WORKER_DOCKERFILE" ]]
}

log_deploy_summary() {
  log "=== deploy summary ==="
  log "  frontend:    ${FRONTEND_ACTION}"
  log "  homepage:    ${HOMEPAGE_ACTION}"
  log "  panel:       ${PANEL_ACTION}"
  log "  worker:      ${WORKER_ACTION}"
  log "  playwright:  ${PLAYWRIGHT_ACTION}"
  log "  propagator:  ${PROPAGATOR_ACTION}"
  log "  elapsed:     ${SECONDS}s"
}

cmd_check() {
  local panel_hash worker_hash saved
  log "=== deploy check (no rsync, no docker writes) ==="
  preflight_local || die "local preflight failed"
  DRY_RUN=1
  maybe_build_frontend
  maybe_build_homepage
  panel_hash="$(local_image_hash panel)"
  worker_hash="$(local_image_hash worker)"
  log "panel input hash:  ${panel_hash:0:12}…"
  log "worker input hash: ${worker_hash:0:12}…"
  if playwright_sidecar_available; then
    log "playwright input hash: $(local_image_hash playwright-worker | cut -c1-12)…"
  fi
  if [[ "$LOCAL_ONLY" == "1" ]] || [[ ! -f "$STATE_FILE" ]]; then
    log "local-only — skip SSH image plan (no aws-postgres.env or --local)"
    log_deploy_summary
    return 0
  fi
  load_state
  if [[ ! -f "$EC2_SSH_KEY" ]]; then
    log "WARN SSH key missing — skip remote plan"
    log_deploy_summary
    return 0
  fi
  remote_assert_db_safe "check" || true
  remote_assert_disk warn
  saved="$(remote_saved_hash panel || true)"
  if [[ -n "$saved" && "$saved" == "$panel_hash" ]]; then
    log "panel: remote hash matches local — would skip docker build (unless --force / missing image)"
  else
    log "panel: local hash differs from remote saved — would rebuild after sync"
  fi
  saved="$(remote_saved_hash worker || true)"
  if [[ -n "$saved" && "$saved" == "$worker_hash" ]]; then
    log "worker: remote hash matches local — would skip docker build (unless --force / missing image)"
  else
    log "worker: local hash differs from remote saved — would rebuild after sync"
  fi
  log_deploy_summary
}

cmd_deploy() {
  local deploy_t0=$SECONDS
  load_state
  if [[ "$DRY_RUN" == "1" ]]; then
    cmd_check
    return 0
  fi

  local redis_pass db_url redis_url secret admin_emails_value
  local google_id google_secret google_redirect panel_public allow_register
  local nowpayments_key nowpayments_secret nowpayments_sandbox_flag
  local sqs_url aws_key aws_secret aws_region
  redis_pass="$(redis_password)"
  secret="$(panel_secret)"
  admin_emails_value="$(admin_emails)"
  google_id="$(google_client_id)"
  google_secret="$(google_client_secret)"
  google_redirect="$(google_redirect_uri)"
  panel_public="$(panel_public_base_url)"
  allow_register="$(panel_allow_register)"
  nowpayments_key="$(nowpayments_api_key)"
  nowpayments_secret="$(nowpayments_ipn_secret)"
  nowpayments_sandbox_flag="$(nowpayments_sandbox)"
  sqs_url="$(sqs_queue_url)"
  aws_key="$(aws_access_key)"
  aws_secret="$(aws_secret_key)"
  aws_region="$(aws_region_name)"
  db_url="postgresql://${DB_USER:-relocation}:${DB_PASSWORD}@172.17.0.1:5432/${DB_NAME:-relocation_jobs}?sslmode=prefer"
  redis_url="redis://:${redis_pass}@172.17.0.1:6379/0"

  phase "preflight" preflight_deploy
  phase "sync" cmd_sync
  phase "prune-before" remote_docker_prune "" "before builds"

  phase "build-panel" maybe_rebuild_image panel "$PANEL_IMAGE" Dockerfile.ec2 PANEL_ACTION
  phase "build-worker" maybe_rebuild_image worker "$WORKER_IMAGE" Dockerfile.ec2-worker WORKER_ACTION
  if [[ -n "${sqs_url}" ]]; then
    phase "build-propagator" maybe_rebuild_image propagator "$PROPAGATOR_IMAGE" apps/role-propagator/Dockerfile PROPAGATOR_ACTION
  else
    PROPAGATOR_ACTION=skipped
    log "Role propagator image skipped — set SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL in .env"
  fi
  if playwright_sidecar_requested; then
    playwright_sidecar_available || die "DEPLOY_PLAYWRIGHT_WORKER=1 but ${PLAYWRIGHT_WORKER_DOCKERFILE} is missing (PR #6 light-worker split)"
    phase "build-playwright" maybe_rebuild_image playwright-worker "$PLAYWRIGHT_WORKER_IMAGE" "$PLAYWRIGHT_WORKER_DOCKERFILE" PLAYWRIGHT_ACTION
  else
    PLAYWRIGHT_ACTION=skipped
  fi

  log "phase start: run-containers (images ready; swapping app containers only)"
  assert_unprotected_name "$PANEL_CONTAINER"
  assert_unprotected_name "$MCP_CONTAINER"
  assert_unprotected_name "$WORKER_CONTAINER"
  assert_unprotected_name "$PROPAGATOR_CONTAINER"
  assert_unprotected_name "$CADDY_CONTAINER"
  assert_unprotected_name "$ALLOY_CONTAINER"
  remote_assert_db_safe "before container swap"

  log "Starting panel container..."
  ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${PANEL_CONTAINER} 2>/dev/null || true
docker run -d --name ${PANEL_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -p ${PANEL_PORT}:${PANEL_PORT} \\
  -v ${REMOTE_DIR}/relocation_jobs/static:/app/relocation_jobs/static:ro \\
  -e PORT=${PANEL_PORT} \\
  -e PANEL_SCRAPE_ENABLED=0 \\
  -e PANEL_COMPANY_FETCH_ENABLED=1 \\
  -e PANEL_DATA_DIR=/tmp/panel-data \\
  -e PANEL_SECRET_KEY=$(q "$secret") \\
  -e PANEL_ADMIN_USER=admin \\
  -e PANEL_ADMIN_EMAILS=$(q "$admin_emails_value") \\
  -e GOOGLE_CLIENT_ID=$(q "$google_id") \\
  -e GOOGLE_CLIENT_SECRET=$(q "$google_secret") \\
  -e GOOGLE_REDIRECT_URI=$(q "$google_redirect") \\
  -e PANEL_PUBLIC_BASE_URL=$(q "$panel_public") \\
  -e PANEL_ALLOW_REGISTER=$(q "$allow_register") \\
  -e NOWPAYMENTS_API_KEY=$(q "$nowpayments_key") \\
  -e NOWPAYMENTS_IPN_SECRET=$(q "$nowpayments_secret") \\
  -e NOWPAYMENTS_SANDBOX=$(q "$nowpayments_sandbox_flag") \\
  -e SESSION_COOKIE_SECURE=1 \\
  -e FETCH_SCHEDULE_ENABLED=1 \\
  -e FETCH_SCHEDULE_INTERVAL_HOURS=6 \\
  -e FETCH_SCHEDULE_CONCURRENCY=2 \\
  -e DATABASE_URL=$(q "$db_url") \\
  -e REDIS_URL=$(q "$redis_url") \\
  -e MCP_PUBLIC_BASE_URL=$(q "$MCP_PUBLIC_BASE_URL") \\
  -e AWS_REGION=$(q "$aws_region") \\
  -e SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$(q "$sqs_url") \\
  -e AWS_ACCESS_KEY_ID=$(q "$aws_key") \\
  -e AWS_SECRET_ACCESS_KEY=$(q "$aws_secret") \\
  ${PANEL_IMAGE}
EOF

  log "Starting MCP container..."
  ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${MCP_CONTAINER} 2>/dev/null || true
docker run -d --name ${MCP_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -p ${MCP_PORT}:${MCP_PORT} \\
  --entrypoint ./docker-entrypoint-mcp.sh \\
  -e MCP_HTTP_HOST=0.0.0.0 \\
  -e MCP_HTTP_PORT=${MCP_PORT} \\
  -e MCP_PUBLIC_BASE_URL=$(q "$MCP_PUBLIC_BASE_URL") \\
  -e DATABASE_URL=$(q "$db_url") \\
  -e REDIS_URL=$(q "$redis_url") \\
  ${PANEL_IMAGE}
EOF

  if [[ -n "${sqs_url}" ]]; then
    log "Starting role propagator container..."
    ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${PROPAGATOR_CONTAINER} 2>/dev/null || true
docker run -d --name ${PROPAGATOR_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -e DATABASE_URL=$(q "$db_url") \\
  -e AWS_REGION=$(q "$aws_region") \\
  -e SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$(q "$sqs_url") \\
  -e AWS_ACCESS_KEY_ID=$(q "$aws_key") \\
  -e AWS_SECRET_ACCESS_KEY=$(q "$aws_secret") \\
  -e PANEL_ADMIN_EMAILS=$(q "$admin_emails_value") \\
  -e PANEL_ADMIN_USER=admin \\
  ${PROPAGATOR_IMAGE}
EOF
  else
    log "Role propagator skipped — set SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL in .env"
    rm_app_container "$PROPAGATOR_CONTAINER"
  fi

  log "Starting fetch worker container..."
  ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${WORKER_CONTAINER} 2>/dev/null || true
docker run -d --name ${WORKER_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -e PANEL_SCRAPE_ENABLED=1 \\
  -e FETCH_SCHEDULE_ENABLED=1 \\
  -e FETCH_SCHEDULE_INTERVAL_HOURS=6 \\
  -e FETCH_SCHEDULE_CONCURRENCY=2 \\
  -e FETCH_COMPANY_TIMEOUT_SECONDS=300 \\
  -e FETCH_COUNTRY_TIMEOUT_SECONDS=2700 \\
  -e PLAYWRIGHT_BOARD_TIMEOUT_SECONDS=90 \\
  -e PANEL_ADMIN_USER=admin \\
  -e PANEL_ADMIN_EMAILS=$(q "$admin_emails_value") \\
  -e DATABASE_URL=$(q "$db_url") \\
  -e AWS_REGION=$(q "$aws_region") \\
  -e SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$(q "$sqs_url") \\
  -e AWS_ACCESS_KEY_ID=$(q "$aws_key") \\
  -e AWS_SECRET_ACCESS_KEY=$(q "$aws_secret") \\
  ${WORKER_IMAGE}
EOF

  start_playwright_worker_container "$db_url" "$admin_emails_value" "$sqs_url" "$aws_region" "$aws_key" "$aws_secret"

  log "Starting Caddy reverse proxy..."
  ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${CADDY_CONTAINER} 2>/dev/null || true
docker run -d --name ${CADDY_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -p 80:80 -p 443:443 \\
  --add-host=host.docker.internal:host-gateway \\
  -v ${REMOTE_DIR}/deploy/ec2/Caddyfile:/etc/caddy/Caddyfile:ro \\
  -v relocation_caddy_data:/data \\
  -v relocation_caddy_config:/config \\
  caddy:2-alpine
EOF

  start_alloy_container
  log "phase done:  run-containers ($((SECONDS - deploy_t0))s wall includes builds)"

  # Dangling images only — keep BuildKit cache for the next deploy.
  phase "prune-after" remote_docker_prune "" "after deploy"
  # open-sg is intentional/manual — do not reopen 0.0.0.0/0 on every deploy.
  cmd_status
  log_deploy_summary
}

start_playwright_worker_container() {
  local db_url="$1" admin_emails_value="$2" sqs_url="$3" aws_region="$4" aws_key="$5" aws_secret="$6"
  assert_unprotected_name "$PLAYWRIGHT_WORKER_CONTAINER"
  if ! playwright_sidecar_requested; then
    log "Playwright sidecar skipped — set DEPLOY_PLAYWRIGHT_WORKER=1 after the light-worker split (PR #6)"
    rm_app_container "$PLAYWRIGHT_WORKER_CONTAINER"
    PLAYWRIGHT_ACTION=skipped
    return 0
  fi
  playwright_sidecar_available || die "DEPLOY_PLAYWRIGHT_WORKER=1 but ${PLAYWRIGHT_WORKER_DOCKERFILE} is missing"
  log "Starting Playwright fetch worker container..."
  ssh_cmd bash -s <<EOF
set -euo pipefail
docker rm -f ${PLAYWRIGHT_WORKER_CONTAINER} 2>/dev/null || true
docker run -d --name ${PLAYWRIGHT_WORKER_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  -e PANEL_SCRAPE_ENABLED=1 \\
  -e FETCH_SCHEDULE_ENABLED=1 \\
  -e FETCH_SCHEDULE_INTERVAL_HOURS=6 \\
  -e FETCH_SCHEDULE_CONCURRENCY=1 \\
  -e FETCH_WORKER_KIND=playwright \\
  -e FETCH_LISTING_CHECK_ENABLED=0 \\
  -e FETCH_COMPANY_TIMEOUT_SECONDS=300 \\
  -e FETCH_COUNTRY_TIMEOUT_SECONDS=2700 \\
  -e PLAYWRIGHT_BOARD_TIMEOUT_SECONDS=90 \\
  -e PANEL_ADMIN_USER=admin \\
  -e PANEL_ADMIN_EMAILS=$(q "$admin_emails_value") \\
  -e DATABASE_URL=$(q "$db_url") \\
  -e AWS_REGION=$(q "$aws_region") \\
  -e SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$(q "$sqs_url") \\
  -e AWS_ACCESS_KEY_ID=$(q "$aws_key") \\
  -e AWS_SECRET_ACCESS_KEY=$(q "$aws_secret") \\
  ${PLAYWRIGHT_WORKER_IMAGE}
EOF
}

start_alloy_container() {
  if ! grafana_cloud_configured; then
    log "Alloy skipped — set GRAFANA_CLOUD_PROMETHEUS_URL, GRAFANA_CLOUD_PROMETHEUS_USER, GRAFANA_CLOUD_API_TOKEN in .env"
    ssh_cmd "docker rm -f ${ALLOY_CONTAINER} 2>/dev/null || true" || true
    return 0
  fi
  local url user token loki_url loki_user
  url="$(grafana_cloud_url)"
  user="$(grafana_cloud_user)"
  token="$(grafana_cloud_token)"
  loki_url="$(grafana_cloud_loki_url)"
  loki_user="$(grafana_cloud_loki_user)"
  if grafana_cloud_loki_configured; then
    log "Starting Grafana Alloy (metrics + logs → Grafana Cloud)..."
    ssh_cmd bash -s <<EOF
set -euo pipefail
docker pull ${ALLOY_IMAGE}
docker rm -f ${ALLOY_CONTAINER} 2>/dev/null || true
cp ${REMOTE_DIR}/deploy/ec2/config.alloy /tmp/alloy-config.alloy
docker run -d --name ${ALLOY_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  --privileged \\
  --pid=host \\
  --add-host=host.docker.internal:host-gateway \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  -v /var/run:/var/run:ro \\
  -v /sys:/sys:ro \\
  -v /sys:/host/sys:ro \\
  -v /proc:/host/proc:ro \\
  -v /:/host/root:ro,rslave \\
  -v /var/lib/docker/:/var/lib/docker:ro \\
  -v /tmp/alloy-config.alloy:/etc/alloy/config.alloy:ro \\
  -e GRAFANA_CLOUD_PROMETHEUS_URL=$(q "$url") \\
  -e GRAFANA_CLOUD_PROMETHEUS_USER=$(q "$user") \\
  -e GRAFANA_CLOUD_API_TOKEN=$(q "$token") \\
  -e GRAFANA_CLOUD_LOKI_URL=$(q "$loki_url") \\
  -e GRAFANA_CLOUD_LOKI_USER=$(q "$loki_user") \\
  -e HOSTNAME=kuchup-ec2 \\
  ${ALLOY_IMAGE} run /etc/alloy/config.alloy \\
    --storage.path=/tmp/alloy \\
    --server.http.listen-addr=0.0.0.0:12345
EOF
  else
    log "Starting Grafana Alloy (metrics only — set GRAFANA_CLOUD_LOKI_URL and GRAFANA_CLOUD_LOKI_USER for logs)"
    ssh_cmd bash -s <<EOF
set -euo pipefail
docker pull ${ALLOY_IMAGE}
docker rm -f ${ALLOY_CONTAINER} 2>/dev/null || true
awk '\$0=="// LOKI_BEGIN"{exit} {print}' ${REMOTE_DIR}/deploy/ec2/config.alloy > /tmp/alloy-config.alloy
docker run -d --name ${ALLOY_CONTAINER} --restart unless-stopped \\
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \\
  --privileged \\
  --pid=host \\
  --add-host=host.docker.internal:host-gateway \\
  -v /var/run/docker.sock:/var/run/docker.sock:ro \\
  -v /var/run:/var/run:ro \\
  -v /sys:/sys:ro \\
  -v /sys:/host/sys:ro \\
  -v /proc:/host/proc:ro \\
  -v /:/host/root:ro,rslave \\
  -v /var/lib/docker/:/var/lib/docker:ro \\
  -v /tmp/alloy-config.alloy:/etc/alloy/config.alloy:ro \\
  -e GRAFANA_CLOUD_PROMETHEUS_URL=$(q "$url") \\
  -e GRAFANA_CLOUD_PROMETHEUS_USER=$(q "$user") \\
  -e GRAFANA_CLOUD_API_TOKEN=$(q "$token") \\
  -e GRAFANA_CLOUD_LOKI_URL=$(q "$loki_url") \\
  -e GRAFANA_CLOUD_LOKI_USER=$(q "$loki_user") \\
  -e HOSTNAME=kuchup-ec2 \\
  ${ALLOY_IMAGE} run /etc/alloy/config.alloy \\
    --storage.path=/tmp/alloy \\
    --server.http.listen-addr=0.0.0.0:12345
EOF
  fi
}

cmd_image_sizes() {
  load_state
  log "=== Docker image sizes ==="
  ssh_cmd "docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' | grep -E 'relocation-(panel:ec2|fetch-worker:ec2|fetch-worker:playwright|role-propagator:ec2)' || true"
}

cmd_logs() {
  load_state
  local follow_flag="" containers c
  [[ "$LOG_FOLLOW" == "1" ]] && follow_flag="-f"
  if [[ "$LOG_SERVICE" == "all" ]]; then
    containers="$PANEL_CONTAINER $CADDY_CONTAINER $MCP_CONTAINER $WORKER_CONTAINER $PLAYWRIGHT_WORKER_CONTAINER $PROPAGATOR_CONTAINER $ALLOY_CONTAINER"
  else
    c="$(container_for_log_service "$LOG_SERVICE")" || die "Unknown log service: $LOG_SERVICE (panel|caddy|mcp|worker|playwright-worker|propagator|alloy|pg|redis|all)"
    containers="$c"
  fi
  for c in $containers; do
    log "=== docker logs $c (tail ${TAIL_N}) ==="
    # shellcheck disable=SC2086
    ssh_cmd "docker logs $c --tail ${TAIL_N} ${follow_flag} 2>&1" || log "  ($c not running)"
    [[ "$LOG_FOLLOW" == "1" ]] && break
  done
}

cmd_status() {
  load_state
  local domain="${PANEL_DOMAIN:-kuchup.com}"
  local panel_code domain_code ip_code mcp_code mcp_domain_code verdict
  local disk_line mem_line

  log "=== Host resources ==="
  disk_line="$(ssh_cmd "df -h / | tail -1" 2>/dev/null || echo "?")"
  mem_line="$(ssh_cmd "free -m | awk 'NR==2{printf \"Mem used=%sMi available=%sMi total=%sMi\", \$3, \$7, \$2}'" 2>/dev/null || echo "?")"
  log "  disk: ${disk_line}"
  log "  mem:  ${mem_line}"
  ssh_cmd "uptime" 2>/dev/null || true
  local usep
  usep="$(ssh_cmd "df -P / | awk 'NR==2{gsub(/%/,\"\",\$5); print \$5}'" 2>/dev/null || echo 0)"
  if [[ "$usep" =~ ^[0-9]+$ ]] && (( usep >= 85 )); then
    log "  WARN: root disk ${usep}% used (>=85%)"
  fi

  log "=== Containers ==="
  ssh_cmd "docker ps -a --filter name=relocation- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
  ssh_cmd "docker ps -a --filter name=^pg\$ --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" || true
  log "Restart / OOM:"
  ssh_cmd bash -s <<'EOF' || true
for c in relocation-panel relocation-caddy relocation-mcp relocation-fetch-worker relocation-playwright-worker relocation-role-propagator relocation-alloy pg relocation-redis; do
  docker inspect -f '{{.Name}} restart={{.RestartCount}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}} status={{.State.Status}}' "$c" 2>/dev/null || true
done
EOF

  log "Panel/Caddy log tails (20):"
  ssh_cmd "docker logs ${PANEL_CONTAINER} --tail 20 2>&1" || log "  panel not running"
  ssh_cmd "docker logs ${CADDY_CONTAINER} --tail 20 2>&1" || log "  caddy not running"
  log "Fetch worker logs (last 20 lines):"
  ssh_cmd "docker logs ${WORKER_CONTAINER} --tail 20 2>&1" || log "  worker not running"
  log "Playwright worker logs (last 20 lines):"
  ssh_cmd "docker logs ${PLAYWRIGHT_WORKER_CONTAINER} --tail 20 2>&1" || log "  playwright worker not running"
  log "Role propagator logs (last 20 lines):"
  ssh_cmd "docker logs ${PROPAGATOR_CONTAINER} --tail 20 2>&1" || log "  propagator not running"

  log "Panel health (localhost:${PANEL_PORT} on EC2):"
  panel_code="$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:${PANEL_PORT}/api/health" 2>/dev/null || echo 000)"
  if [[ "$panel_code" == "200" ]]; then
    log "  http://127.0.0.1:${PANEL_PORT}/api/health -> ${panel_code} (OK)"
  else
    log "  http://127.0.0.1:${PANEL_PORT}/api/health -> ${panel_code} (FAILED)"
  fi

  log "MCP health (localhost:${MCP_PORT} on EC2):"
  mcp_code="$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:${MCP_PORT}/healthz" 2>/dev/null || echo 000)"
  if [[ "$mcp_code" == "200" ]]; then
    log "  http://127.0.0.1:${MCP_PORT}/healthz -> ${mcp_code} (OK)"
  else
    log "  http://127.0.0.1:${MCP_PORT}/healthz -> ${mcp_code} (FAILED)"
  fi

  log "Panel health (via domain):"
  domain_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "https://${domain}/api/health" 2>/dev/null || echo 000)"
  if [[ "$domain_code" == "200" ]]; then
    log "  https://${domain}/api/health -> ${domain_code} (OK)"
  else
    log "  https://${domain}/api/health -> ${domain_code} (check DNS/TLS if deploy just finished)"
  fi

  log "MCP health (via domain):"
  mcp_domain_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "https://mcp.kuchup.com/healthz" 2>/dev/null || echo 000)"
  if [[ "$mcp_domain_code" == "200" ]]; then
    log "  https://mcp.kuchup.com/healthz -> ${mcp_domain_code} (OK)"
  else
    log "  https://mcp.kuchup.com/healthz -> ${mcp_domain_code} (check DNS/TLS if deploy just finished)"
  fi

  log "Origin lock-down (Elastic IP, expect 404):"
  ip_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${ELASTIC_IP}/api/health" 2>/dev/null || echo 000)"
  log "  http://${ELASTIC_IP}/api/health -> ${ip_code}"

  if [[ "$panel_code" == "200" && "$domain_code" == "200" ]]; then
    verdict=all_ok
  elif [[ "$panel_code" == "200" && "$domain_code" != "200" ]]; then
    verdict=origin_ok_cf_fail
  elif [[ "$panel_code" != "200" ]]; then
    verdict=panel_down
  else
    verdict=degraded
  fi
  log "=== Layer verdict: ${verdict} ==="
}

# Parse global flags then dispatch (--force may appear anywhere).
ACTION=deploy
TAIL_N=100
USAGE="Usage: $0 {check|sync|deploy|prune|open-sg|status|logs|worker-logs|image-sizes} [--force|--dry-run|--local]"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE_REBUILD=1
      shift
      ;;
    --dry-run|--check)
      DRY_RUN=1
      shift
      ;;
    --local)
      LOCAL_ONLY=1
      DRY_RUN=1
      shift
      ;;
    -f|--follow)
      LOG_FOLLOW=1
      shift
      ;;
    check|sync|deploy|prune|open-sg|status|worker-logs|image-sizes|logs)
      ACTION="$1"
      shift
      ;;
    *)
      if [[ "$ACTION" == "worker-logs" && "$1" =~ ^[0-9]+$ ]]; then
        TAIL_N="$1"
        shift
      elif [[ "$ACTION" == "logs" ]]; then
        if [[ "$1" =~ ^[0-9]+$ ]]; then
          TAIL_N="$1"
        elif [[ "$1" == "-f" || "$1" == "--follow" ]]; then
          LOG_FOLLOW=1
        else
          LOG_SERVICE="$1"
        fi
        shift
      else
        die "$USAGE"
      fi
      ;;
  esac
done

case "$ACTION" in
  check) cmd_check ;;
  sync) cmd_sync ;;
  deploy) cmd_deploy ;;
  prune) cmd_prune ;;
  open-sg) cmd_open_sg ;;
  status) load_state; cmd_status ;;
  logs) cmd_logs ;;
  worker-logs)
    load_state
    LOG_SERVICE=worker
    LOG_FOLLOW=1
    cmd_logs
    ;;
  image-sizes)
    load_state
    cmd_image_sizes
    ;;
  *) die "$USAGE" ;;
esac
