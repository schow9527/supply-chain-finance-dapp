# Production deployment runbook

This runbook prepares a Render Web service with a Persistent Disk, an event Worker, and Render PostgreSQL. The existing S3-compatible backend remains the recommended long-term alternative. This document does not authorize deployment or any on-chain write. Never paste a database password, RPC URL, S3 secret, wallet private key, mnemonic, session secret, signed message, or Authorization header into chat or logs.

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

Set `WEB3_PROVIDER_URI` locally without printing or sharing it. Run `flask --app app:app production-preflight --role worker` under production configuration. It checks chain ID `11155111`, latest block against start block `11868898`, all five deployments, required ABI views, cross-contract references, and sync state. The Web-specific command is `production-preflight --role web`; it validates PostgreSQL, migrations, configuration, session secret, contract deployment file, and PDF storage without requiring Worker sync completion. Neither command signs or sends a transaction.

To scan events against isolated `_test` PostgreSQL, run `flask --app app:app sync-events --once` twice, and compare `synced_events`, `flask --app app:app sync-status`, `chain_events`, and projection counts. The second unchanged run must add zero events. Validate sampled transaction hashes, block numbers, contract addresses, log indexes, decoded event names, and transaction/log order against read-only RPC results. Large result sets are automatically bisected without skipping blocks.

## Render Persistent Disk

The course deployment uses `STORAGE_BACKEND=render_disk` with both `RENDER_DISK_MOUNT_PATH` and `UPLOAD_FOLDER` set to `/opt/render/project/src/uploads`. The Blueprint attaches the 1 GB `invoice-pdf-data` disk to the Web service only. Files are written with mode `0600` using a same-directory temporary file, `fsync`, and atomic rename. Keys remain relative UUID paths and downloads always pass through Session/role authorization.

This is not equivalent to object storage. Render documents that a disk is available to only one runtime instance, cannot be shared with the Worker, prevents horizontal scaling and zero-downtime deployment, and is unavailable during build, pre-deploy, and one-off jobs. Consequently the Worker never initializes PDF storage, Web `numInstances` is fixed at one, and runtime readiness—not the migration pre-deploy instance—performs the disk write/space probe. Expect a short outage on deploy.

Only files below the mount survive restarts. After first deployment, upload a normal course-test invoice through the authenticated UI/API, record its application invoice ID/hash (not a server path), redeploy Web, and download the same invoice again. Do not upload a diagnostic PDF from `post-deploy-verify`; that command is read-only. Monitor Render disk usage. Define a daily export/backup owner and periodically test restore according to the Render plan's snapshot/export capabilities.

## Private S3-compatible storage

The bucket must remain private. The Web identity needs bucket health plus object read/write/delete only under its configured `S3_KEY_PREFIX`; it does not need bucket-policy administration or broad account permissions. PDFs use `invoices/<chain_id>/<supplier_lower>/<uuid>.pdf`. Downloads are authenticated and proxied by the backend, so browser CORS is not required.

Configure `STORAGE_BACKEND=s3`, endpoint (optional for AWS), region, bucket, access key, secret, and prefix as deployment secrets. Run the opt-in smoke test only against an explicitly designated test bucket:

```powershell
$env:S3_TEST_BUCKET = '<private test bucket>'
python -m pytest -m s3 -q
```

It creates, reads, and deletes exactly one UUID-named object; it never lists or empties the bucket. To migrate from Disk to S3, provision a private bucket and least-privilege credentials, copy and verify every stored key out of band, switch the Web secrets to `STORAGE_BACKEND=s3`, remove the Blueprint disk only after validation and backup retention, then redeploy. Verify authorized downloads and `403` for an unrelated wallet before considering scale-out.

## Render deployment and rollback

`render.yaml` defines Web (`gunicorn app:app`), Worker (`python -m backend.worker`), and PostgreSQL in Singapore. Both receive the database via `fromDatabase`. Web has the PDF disk, `PROCESS_ROLE=web`, and `EVENT_SYNC_ENABLED=false`; Worker has no disk, uses `PROCESS_ROLE=worker`, and enables event sync. Web `preDeployCommand` runs `flask --app app:app db upgrade` once. The Worker never migrates.

The Blueprint intentionally selects the smallest current paid compute plans (`0.5c-512mb` Web/Worker and `0.1c-256mb` PostgreSQL). Render documents pre-deploy commands as a paid-service feature, and background workers do not have a free production tier. If the selected account cannot use pre-deploy, remove that field only after establishing a single controlled migration from a trusted machine before each Web deployment; never move migrations into build/start or run them concurrently in Web and Worker. Validate the Blueprint with Render CLI before sync. References: [Blueprint YAML](https://render.com/docs/blueprint-spec), [deploy commands](https://render.com/docs/deploys), and [compute plans](https://render.com/docs/compute-plans).

First deployment procedure:

1. Create the Blueprint without deploying until the private RPC secret is entered in the Render Dashboard. Never send the RPC URL through chat.
2. Confirm Blueprint-created PostgreSQL and the Web disk are in the same region as Web/Worker.
3. Deploy database/migration, then Web, then Worker; confirm the migration is at head.
4. Run `production-preflight --role web`, `production-preflight --role worker`, and `post-deploy-verify` in an appropriate runtime context.
5. Verify live/ready, authenticated PDF upload/download, and `sync-status`.
6. Redeploy Web and prove the previously uploaded PDF remains downloadable.
7. Restart Worker and prove events/projections do not duplicate.

For rollback, stop Worker first and restore the prior Web/Worker release. The same Web disk remains attached, but deployment is not zero-downtime. Do not automatically downgrade a database containing new writes. Back up and prove downgrade compatibility before one controlled migration. Restart Worker and recheck cursor hash/idempotence afterward.

Readiness is non-200 for database, migration, invalid configuration, or storage failures. Temporary RPC or sync lag/not-started remains `200` with `status=degraded`. Storage output contains only backend, status, and a coarse free-space category—never an absolute path or file list.
