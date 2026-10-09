# Production deployment runbook

This runbook prepares a Render Web service, event Worker, Render PostgreSQL, and a private S3-compatible bucket. It does not authorize deployment or any on-chain write. Never paste a database password, RPC URL, S3 secret, wallet private key, mnemonic, session secret, signed message, or Authorization header into chat or logs.

## Local PostgreSQL validation

Create a dedicated database whose name visibly contains `_test`, for example `scf_dapp_test`. Set `POSTGRES_TEST_URL` only in the local shell or an untracked `.env`; URLs using `postgres://` or `postgresql://` are normalized to the SQLAlchemy `postgresql+psycopg://` driver. Localhost is accepted automatically. A remote dedicated test host additionally requires `POSTGRES_TEST_ALLOWED_HOST` to exactly match its hostname.

```powershell
$env:POSTGRES_TEST_URL = '<secret PostgreSQL test URL for an _test database>'
python -m pytest -m postgres -q
```

The integration test performs upgrade/check, downgrade-to-base, upgrade/check, and validates `NUMERIC(78,0)`, JSON, timezone-aware timestamps, unique constraints, rollback, worker batch rollback, projections, rebuild, and a query API. It is destructive to that dedicated database. Never point it at production. To remove the database, first disconnect all clients, independently verify the selected server and database name contains `_test`, then use PostgreSQL administrator tooling to drop that exact database—never a wildcard or production connection.

For a normal application migration:

```powershell
flask --app app:app db upgrade
flask --app app:app db check
```

## Sepolia read-only validation

Set `WEB3_PROVIDER_URI` locally without printing or sharing it. Then run `flask --app app:app production-preflight` under production configuration. It checks chain ID `11155111`, latest block against start block `11868898`, all five deployments, the required ABI view calls, and cross-contract references. It never signs or sends a transaction.

To scan events against isolated `_test` PostgreSQL, run `flask --app app:app sync-events --once` twice, and compare `synced_events`, `flask --app app:app sync-status`, `chain_events`, and projection counts. The second unchanged run must add zero events. Validate sampled transaction hashes, block numbers, contract addresses, log indexes, decoded event names, and transaction/log order against read-only RPC results. Large result sets are automatically bisected without skipping blocks.

## Private S3-compatible storage

The bucket must remain private. The Web identity needs bucket health plus object read/write/delete only under its configured `S3_KEY_PREFIX`; it does not need bucket-policy administration or broad account permissions. PDFs use `invoices/<chain_id>/<supplier_lower>/<uuid>.pdf`. Downloads are authenticated and proxied by the backend, so browser CORS is not required.

Configure `STORAGE_BACKEND=s3`, endpoint (optional for AWS), region, bucket, access key, secret, and prefix as deployment secrets. Run the opt-in smoke test only against an explicitly designated test bucket:

```powershell
$env:S3_TEST_BUCKET = '<private test bucket>'
python -m pytest -m s3 -q
```

It creates, reads, and deletes exactly one UUID-named object; it never lists or empties the bucket. Verify an authorized user can upload/download and an unrelated wallet receives `403`.

## Render deployment and rollback

`render.yaml` defines Web (`gunicorn app:app`), Worker (`python -m backend.worker`), and PostgreSQL in Singapore. Both processes receive the database via `fromDatabase`; Web has private S3 and `EVENT_SYNC_ENABLED=false`; Worker has `EVENT_SYNC_ENABLED=true` and no S3 credentials. Web `preDeployCommand` runs `flask --app app:app db upgrade` once. Builds and process startup never migrate.

The Blueprint intentionally selects the smallest current paid compute plans (`0.5c-512mb` Web/Worker and `0.1c-256mb` PostgreSQL). Render documents pre-deploy commands as a paid-service feature, and background workers do not have a free production tier. If the selected account cannot use pre-deploy, remove that field only after establishing a single controlled migration from a trusted machine before each Web deployment; never move migrations into build/start or run them concurrently in Web and Worker. Validate the Blueprint with Render CLI before sync. References: [Blueprint YAML](https://render.com/docs/blueprint-spec), [deploy commands](https://render.com/docs/deploys), and [compute plans](https://render.com/docs/compute-plans).

First deployment procedure:

1. Create/verify the private bucket and least-privilege Web credentials.
2. Create the Blueprint without deploying until every `sync: false` secret is entered.
3. Run production preflight locally against intended dependencies.
4. Deploy database/migration, then Web, then Worker.
5. Verify live/ready, migration head, upload/download authorization, and sync status.
6. Restart Worker once and prove events/projections do not duplicate.

For rollback, stop Worker first and restore the prior Web/Worker release. Do not automatically downgrade a database containing new writes. Back up and prove downgrade compatibility before one controlled migration. Restart Worker and recheck cursor hash/idempotence afterward.

Readiness is non-200 only for database, migration, or invalid configuration failures. Temporary RPC, sync lag/not-started, or storage-health failures return `200` with `status=degraded`.
