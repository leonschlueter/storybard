#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
MODEL_NOTE="${MODEL_NOTE:-mistral}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need curl
need jq

echo "== Storybard CLI =="
echo "API: $API_URL"
echo "This will seed a new campaign every run."

SEED_JSON=$(curl -sS -X POST "$API_URL/v1/dev/seed" \
  -H "Content-Type: application/json" \
  -d '{"name":"CLI Test Campaign","narration_style":"basic_fantasy","genre":"fantasy","themes":["mystery","frontier"],"magic_level":"medium","constraints":["medium world","3-5 threads","playable starting town"]}')

CAMPAIGN_ID=$(echo "$SEED_JSON" | jq -r '.campaign_id')
ACTOR_ID=$(echo "$SEED_JSON" | jq -r '.player_actor_id')

echo "Seeded campaign: $CAMPAIGN_ID"
echo "Player actor: $ACTOR_ID"
echo

PENDING_ID=""

while true; do
  if [[ -n "${PENDING_ID}" ]]; then
    echo -n "Enter raw d20 roll (1-20) for pending roll ${PENDING_ID}: "
    read -r ROLL
    RESP=$(curl -sS -X POST "$API_URL/v1/rolls/${PENDING_ID}" \
      -H "Content-Type: application/json" \
      -d "{\"d20\": ${ROLL}}")
    PENDING_ID=""
  else
    echo -n "You> "
    read -r INPUT || exit 0
    if [[ "${INPUT}" == "/quit" ]]; then exit 0; fi
    RESP=$(curl -sS -X POST "$API_URL/v1/turns/${ACTOR_ID}" \
      -H "Content-Type: application/json" \
      -d "{\"text\": $(jq -Rs . <<< "${INPUT}") }")
  fi

  STATUS=$(echo "$RESP" | jq -r '.status')
  if [[ "$STATUS" != "ok" ]]; then
    echo "Error: $(echo "$RESP" | jq -c '.')"
    continue
  fi

  PHASE=$(echo "$RESP" | jq -r '.phase')
  TIME=$(echo "$RESP" | jq -r '.campaign_time')
  MODE=$(echo "$RESP" | jq -r '.mode')

  echo
  echo "[$TIME][$MODE][$PHASE]"
  NARR=$(echo "$RESP" | jq -r '.narration // empty')
  if [[ -n "$NARR" ]]; then
    echo "$NARR"
  fi

  PENDING=$(echo "$RESP" | jq -r '.pending_roll.id // empty')
  if [[ -n "$PENDING" ]]; then
    PENDING_ID="$PENDING"
    PROMPT=$(echo "$RESP" | jq -r '.pending_roll.prompt')
    echo
    echo "== ROLL REQUIRED =="
    echo "$PROMPT"
  fi
  echo
done
