# 后端 API

## Production health and private files

- `GET /api/health/live` reports Web-process liveness only.
- `GET /api/health/ready` is non-200 for database, migration, invalid production configuration, or storage failure. Temporary RPC and sync-lag/not-started conditions return `200` with `status: degraded`.
- Health output excludes database/RPC URLs, storage endpoint queries, secrets, and session data.

`POST /api/invoices/file` validates and hashes a PDF, stores a generated private object, then commits metadata. Storage failure is `STORAGE_UNAVAILABLE`; database failure triggers best-effort object cleanup. `GET /api/invoices/<id>/file` authorizes the supplier, buyer, ADMIN, or AUDITOR and proxies the private attachment.

Keys are `invoices/<chain_id>/<supplier_lower>/<uuid>.pdf`. The sanitized original filename is metadata only; it never controls the object key. `render_disk` paths and file listings are never returned. In S3 mode, buckets are not public and object URLs are neither persisted nor exposed.

所有金额均为 mUSD 的 6 位最小单位，并以十进制字符串返回。Unix 链上时间使用秒；API 日期时间使用 UTC ISO 8601。链上写操作由浏览器 MetaMask 完成，后端不持有私钥。

## 认证与错误

认证流程为 `POST /api/auth/nonce` → 钱包 `signMessage` → `POST /api/auth/verify`。成功后使用 HttpOnly、SameSite=Lax 的同源 Session Cookie；Production Cookie 同时启用 Secure。`POST /api/auth/logout` 清除会话，`GET /api/me` 返回钱包、链上角色和企业申请状态。

错误统一为：

```json
{"error":{"code":"AUTH_REQUIRED","message":"Wallet authentication is required.","details":{}}}
```

## 分页

所有列表接受 `page` 和 `page_size`，默认 1/50，`page_size` 最大 100：

```json
{"items":[],"page":1,"page_size":50,"total":0}
```

浏览器 `ApiClient` 会集中返回 `items`，保持旧页面的数组接口。

## 企业与 PDF

- `POST /api/enterprises`：认证钱包提交或重新提交企业申请。
- `GET /api/enterprises`：ADMIN，可按 `status`、`role_applied` 筛选。
- `PATCH /api/enterprises/<id>`：ADMIN；批准时验证 RoleManager 回执和 RoleGranted。
- `POST /api/invoices/file`：SUPPLIER 上传 PDF 草稿，校验双方角色、文件头、MIME、金额和到期日。
- `GET /api/invoices/<id>/file`：supplier、buyer、ADMIN、AUDITOR 下载。

## 投影查询

- `GET /api/invoices`：支持 `supplier`、`buyer`、`address`、`status`。
- `GET /api/invoices/<id>`：发票详情。
- `GET /api/receivables?holder=0x...`：当前持仓及凭证元数据。
- `GET /api/receivables/<id>/history`：按 block/transaction/log 排序的业务时间线。
- `GET /api/financing`：支持 `status`、supplier Session 范围和 FUNDER 开放市场。
- `GET /api/financing/<id>`：融资申请及全部报价。
- `GET /api/dashboard`：按 Session 链上角色返回真实投影统计；兼容 `receivable_total`、`pending_invoices_count`、`financing_active_amount`、`funded_total_amount`。
- `GET /api/transactions`：按 Session 地址聚合 tx_hash，返回业务 action 和 Etherscan URL。
- `GET /api/events`：支持 `contract`、`name`/`type`、`address`、`from`、`to`。

发票示例：

```json
{"items":[{"id":1,"onchain_id":"7","invoice_no":"INV-7","amount":"1000000","status":"CONFIRMED","file_url":"/api/invoices/1/file"}],"page":1,"page_size":50,"total":1}
```

凭证示例：

```json
{"items":[{"receivable_id":"7","balance":"1000000","face_value":"1000000","status":"ACTIVE","is_frozen":false}],"page":1,"page_size":50,"total":1}
```

## 权限矩阵

| API | SUPPLIER | CORE_ENTERPRISE | FUNDER | AUDITOR | ADMIN |
|---|---|---|---|---|---|
| invoices | 自己开具 | 自己应付 | 否 | 全局 | 全局 |
| receivables | 自己持仓 | 自己持仓 | 自己持仓 | 指定 holder | 指定 holder |
| financing | 自己申请 | 否 | 开放市场/相关报价 | 全局 | 全局 |
| dashboard | 自己 | 自己 | 自己 | 全局统计 | 系统统计 |
| transactions | 自己 | 自己 | 自己 | 自己 | 自己 |
| events | 仅相关事件 | 仅相关事件 | 仅相关事件 | 全局 | 全局 |

## Worker 与状态

```bash
python -m backend.worker
python -m flask --app app:app sync-events --once
python -m flask --app app:app sync-status
python -m flask --app app:app rebuild-projections --confirm
```

Worker 从 `contracts/deployments/11155111.json` 和 `contracts/abi/*.json` 加载地址及 ABI。它只同步到确认后的区块，全局排序五合约日志，并在一个事务中写事件、投影和 cursor。`GET /api/health/ready` 返回 database、rpc、contracts、event_sync、latest/last block、lag 和 last_sync_at，且不会泄漏 RPC URL。
