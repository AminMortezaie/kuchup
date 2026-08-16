# SQS — user opportunity refresh

**Region:** `eu-central-1` (same as EC2 Postgres)  
**Product queue:** `user-opportunity-refresh`  
**Env var:** `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL`  
**Worker:** `python3 scripts/opportunity_sqs_worker.py`  
**Code:** [`relocation_jobs/core/sqs_client.py`](../../relocation_jobs/core/sqs_client.py), [`relocation_jobs/opportunities/`](../../relocation_jobs/opportunities/)

When the env var is **unset**, refresh runs **inline** (sync). That is fine for local/dev.

**Production release posture (2026-08):** keep `SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL` **unset** on panel/fetch until the opportunity worker is deployed and monitored. Interactive `PUT /api/preferences` always refreshes **sync** in-process so the board updates immediately. Do not half-enable SQS (queue URL without a running worker).

Related product design: [entitlements-and-opportunities.md](../reference/entitlements-and-opportunities.md).  
Infra fetch/PDF queues (separate): [multi-user-scaling-proposal.md](../reference/multi-user-scaling-proposal.md).

## What to create

| Queue | Type | Purpose |
|-------|------|---------|
| `user-opportunity-refresh-dlq` | Standard | Failed messages after 3 receives |
| `user-opportunity-refresh` | Standard | Matcher jobs: `{type:user,user_id}` or `{type:country,country}` |

Attributes on the main queue:

- `VisibilityTimeout=60`
- `ReceiveMessageWaitTimeSeconds=10` (long poll)
- `MessageRetentionPeriod=345600` (4 days)
- Redrive: `maxReceiveCount=3` → DLQ

## Create with AWS CLI

Requires `aws` CLI credentials (same as `aws-postgres.env` / `.env` `AWS_ACCESS_KEY_ID`).  
Or run [`scripts/aws_sqs_opportunity_queue.sh`](../../scripts/aws_sqs_opportunity_queue.sh).

```bash
export AWS_REGION=eu-central-1

# 1) DLQ
aws sqs create-queue \
  --region "$AWS_REGION" \
  --queue-name user-opportunity-refresh-dlq

DLQ_URL="$(aws sqs get-queue-url \
  --region "$AWS_REGION" \
  --queue-name user-opportunity-refresh-dlq \
  --query QueueUrl --output text)"

DLQ_ARN="$(aws sqs get-queue-attributes \
  --region "$AWS_REGION" \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --query Attributes.QueueArn --output text)"

# 2) Main queue + redrive
aws sqs create-queue \
  --region "$AWS_REGION" \
  --queue-name user-opportunity-refresh \
  --attributes "{
    \"VisibilityTimeout\": \"60\",
    \"MessageRetentionPeriod\": \"345600\",
    \"ReceiveMessageWaitTimeSeconds\": \"10\",
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"

QUEUE_URL="$(aws sqs get-queue-url \
  --region "$AWS_REGION" \
  --queue-name user-opportunity-refresh \
  --query QueueUrl --output text)"

echo "Set in gitignored .env:"
echo "AWS_REGION=$AWS_REGION"
echo "SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=$QUEUE_URL"
```

Idempotent: `create-queue` on an existing name returns the existing queue.

## Wire into the app

In **gitignored** `.env` (never commit real URLs to the public repo):

```bash
AWS_REGION=eu-central-1
SQS_USER_OPPORTUNITY_REFRESH_QUEUE_URL=https://sqs.eu-central-1.amazonaws.com/<ACCOUNT_ID>/user-opportunity-refresh
```

On EC2 panel/worker containers, pass the same vars (see [`scripts/ec2_app_deploy.sh`](../../scripts/ec2_app_deploy.sh) when extended).

## IAM

Grant the CLI/EC2 identity:

| Action | Resource |
|--------|----------|
| `sqs:SendMessage` | main queue ARN |
| `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` | main queue ARN |
| `sqs:GetQueueAttributes` | DLQ ARN (ops) |

## Run the worker

```bash
# one poll batch
python3 scripts/opportunity_sqs_worker.py --once

# long-running
python3 scripts/opportunity_sqs_worker.py
```

Message bodies:

```json
{"type":"user","user_id":123}
{"type":"country","country":"uk"}
```

## Verify

```bash
# approximate counts
aws sqs get-queue-attributes \
  --region eu-central-1 \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# send a test message (replace USER_ID)
aws sqs send-message \
  --region eu-central-1 \
  --queue-url "$QUEUE_URL" \
  --message-body '{"type":"user","user_id":1}'
```

Then run the worker with `DATABASE_URL` pointing at the same Postgres the panel uses.

## Console

AWS Console → **SQS** → **Create queue** → Standard → `user-opportunity-refresh` → enable dead-letter queue `user-opportunity-refresh-dlq`, max receives `3` → copy URL into `.env`.
