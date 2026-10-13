# Production checklist

## Before authorization

- [ ] Branch/commit reviewed and tracked files contain no secrets.
- [ ] Compile, backend unit/mock tests and coverage pass.
- [ ] Frontend tests and JavaScript syntax checks pass.
- [ ] `pip check` and SQLite migration upgrade/check pass.
- [ ] Dedicated `_test` PostgreSQL passed `pytest -m postgres`; skip means blocked.
- [ ] Render Disk adapter tests pass; S3 adapter tests remain intact.
- [ ] If selecting S3, an explicit private test bucket passed `pytest -m s3`; skip means S3 remains unverified.
- [ ] Real Sepolia read-only preflight passed; missing RPC is `REAL_SEPOLIA_RPC_NOT_CONFIGURED` and blocked.
- [ ] Read-only sync ran twice in isolated PostgreSQL; second run added no events/projections.
- [ ] No private key, mnemonic, signature, Authorization header, complete database/RPC URL, or S3 secret appears in output or tracked files.

## Render

- [ ] Web/Worker share Render PostgreSQL and Sepolia RPC.
- [ ] Web has the `invoice-pdf-data` disk at `/opt/render/project/src/uploads`; Worker has no disk.
- [ ] Web uses `PROCESS_ROLE=web`, `STORAGE_BACKEND=render_disk`, sync false and exactly one instance.
- [ ] Worker uses `PROCESS_ROLE=worker`, `STORAGE_BACKEND=disabled`, sync true.
- [ ] Health path is `/api/health/ready`; migration runs only in Web pre-deploy.
- [ ] Production rejects SQLite/defaults/wrong chain/zero contracts/local storage/debug/testing/role simulation/Web sync.

## After explicit deployment authorization

- [ ] Migration is at head; live and ready are understood.
- [ ] Five contracts and all reference links match.
- [ ] Authorized PDF flow works, unauthorized access fails, and a file remains after a Web redeploy.
- [ ] Disk backup/restore ownership is documented; long-term scale-out migration to S3 is planned.
- [ ] Worker cursor/hash/confirmation lag are correct.
- [ ] Worker restart and second sync create no duplicates.
- [ ] Backup, previous release, migration compatibility, and rollback owner are documented.
