#!/usr/bin/env bash
# Create (or reuse) the user-opportunity-refresh SQS queue + DLQ in eu-central-1.
# Prints the QueueUrl to set as SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL in .env.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REGION="${AWS_REGION:-eu-central-1}"
MAIN_NAME="${SQS_OPPORTUNITY_QUEUE_NAME:-user-opportunity-refresh}"
DLQ_NAME="${SQS_OPPORTUNITY_DLQ_NAME:-user-opportunity-refresh-dlq}"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  # Prefer explicit AWS_* already in the environment; do not override.
  source "$ROOT/.env" 2>/dev/null || true
  set +a
fi

export AWS_REGION="$REGION"

echo "Region: $REGION"
echo "Creating DLQ: $DLQ_NAME"
aws sqs create-queue --region "$REGION" --queue-name "$DLQ_NAME" >/dev/null

DLQ_URL="$(aws sqs get-queue-url --region "$REGION" --queue-name "$DLQ_NAME" --query QueueUrl --output text)"
DLQ_ARN="$(aws sqs get-queue-attributes \
  --region "$REGION" \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --query Attributes.QueueArn --output text)"

echo "Creating main queue: $MAIN_NAME (redrive → DLQ, maxReceiveCount=3)"
# RedrivePolicy must be a JSON *string* inside the Attributes map.
REDRIVE="$(printf '{"deadLetterTargetArn":"%s","maxReceiveCount":"3"}' "$DLQ_ARN")"
ATTRS="$(python3 - <<PY
import json
print(json.dumps({
    "VisibilityTimeout": "60",
    "MessageRetentionPeriod": "345600",
    "ReceiveMessageWaitTimeSeconds": "10",
    "RedrivePolicy": """$REDRIVE""",
}))
PY
)"

aws sqs create-queue \
  --region "$REGION" \
  --queue-name "$MAIN_NAME" \
  --attributes "$ATTRS" >/dev/null

QUEUE_URL="$(aws sqs get-queue-url --region "$REGION" --queue-name "$MAIN_NAME" --query QueueUrl --output text)"

echo
echo "DLQ URL:  $DLQ_URL"
echo "Queue URL: $QUEUE_URL"
echo
echo "Add to gitignored .env (do not commit):"
echo "AWS_REGION=$REGION"
echo "SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$QUEUE_URL"
echo
echo "Worker: go run ./apps/role-propagator --once"
