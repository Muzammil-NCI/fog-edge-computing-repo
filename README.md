# Campus fog/edge

## Prerequisites

- AWS CLI configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Node.js 18+ (for `dashboard`)

## 1) Deploy backend (SAM)

```
sam build
sam deploy --guided
```

When prompted, set **IoTDataEndpoint** to your account’s **Data-ATS endpoint** e.g. `xxxxxx-ats.iot.eu-west-1.amazonaws.com` — **hostname only**, no `https://`.

Optional parameters:

- `IoTPublishTopic` — default `campus/v2/fog/aggregated`
- `EdgeScheduleMinutes` — default `1` (EventBridge cannot go below ~1 minute; steady pacing is done **inside** each edge Lambda with sleeps between SQS sends.)
- `MessagesPerEdgeInvocation` — default `120` per **sensor** Lambda (~60s of pacing at 0.5s between sends). **Four** edge functions run on the same schedule, so SQS receives roughly **4×** as many messages per tick as a single combined edge.
- `EdgeSendIntervalSeconds` — default `0.5` (zones round-robin; each Lambda emits **one** metric only, set by `EDGE_SENSOR_METRIC` in the template). Override `ZONES` env for a custom comma-separated list.
- `FogWindowSeconds` — default `5` (how often fog emits an aggregate per `zone#metric` once samples exist)

After deploy, note outputs:

- `HttpApiUrl` — API Gateway base URL
- `DashboardFetchExample` — sample `GET .../readings?...`

### IoT Core (optional follow-up)

Attach an **IoT Rule** on `IoTPublishTopic` if you want additional cloud routing (S3, OpenSearch, etc.). The fog Lambda already **writes aggregates to DynamoDB** for the dashboard, so a rule is not required for the UI.

### Troubleshooting: no rows in aggregates table / no IoT messages

1. **Flush timing** — Aggregates are emitted on a **wall-clock window** (`WINDOW_SECONDS`, default 30) per `zone#metric`. Until enough wall time passes with at least one buffered sample, nothing is published. Lower `WINDOW_SECONDS` in the fog Lambda environment for faster tests.
2. **CloudWatch** — Fog logs include `iot_publish_ok` / `iot_publish_failed` and `ddb_aggregate_put` (or exceptions). Check for `AccessDeniedException` on `iot:Publish` or DynamoDB errors.
3. **IoT endpoint** — Use the **Data-ATS** hostname only (or full `https://` URL; the code strips the scheme). Wrong region/endpoint = publish fails.
4. **Test client** — In IoT Core → Test → MQTT client, subscribe to `campus/v2/#` (or your `IoTPublishTopic`) with QoS 1.
5. **Concurrency** — Multiple fog invocations can race on the same DynamoDB buffer item; for demos, temporarily set reserved concurrency to **1** on the fog function if aggregates look sparse.

## 2) Build and host the dashboard (S3 static website)

```
cd dashboard
npm install
```

Create `.env.production` (or export for one shot):

```env
VITE_API_BASE=https://xxxxxxxx.execute-api.eu-west-1.amazonaws.com
```

Build:

```powershell
npm run build
```

Upload `dist/` to an S3 bucket configured for static website hosting:

1. Create bucket, enable static website hosting (index = `index.html`).
2. Bucket policy allowing `s3:GetObject` for public read (or front with CloudFront for production).
3. `aws s3 sync dist/ s3://YOUR_BUCKET_NAME --delete`

Open the website endpoint URL; the app polls `GET {VITE_API_BASE}/readings` every 3 seconds.

# 3) Teardown
```powershell
sam delete --stack-name YOUR_STACK_NAME
```
