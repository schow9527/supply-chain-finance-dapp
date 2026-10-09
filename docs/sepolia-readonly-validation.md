# Sepolia read-only validation

Status: **BLOCKED — REAL_SEPOLIA_RPC_NOT_CONFIGURED**

No real RPC URL was present during this preparation. Therefore chain ID, latest block, deployed bytecode, view calls, contract references, receipts, log synchronization, and the idempotent rerun are not reported as passed. No public fallback was substituted, no private key was used, and no transaction was signed or broadcast.

After a local secret is configured, follow `docs/deployment.md`. Record only UTC validation time, chain ID, public contract addresses, bytecode-present flags, non-sensitive view summaries, sync range/count, and second-run new-event count. Never record the RPC URL.
