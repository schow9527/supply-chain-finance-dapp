# Defect Log

> **Owner**: YANG SHUYI (Member 6)
> **Related**: [Test Plan](test-plan.md) · [Test Cases](test-cases.md)

Severity: **P0** main flow blocked / funds incorrect · **P1** feature fails acceptance criteria · **P2** wording, display or usability issue.

## Summary

| ID | Title | Severity | Owner | Found | Status | Fixed in | Retested |
|---|---|---|---|---|---|---|---|
| BUG-01 | Faucet button shows wrong amount | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-02 | Stale session state after switching MetaMask account | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-03 | No UI to grant Auditor / Admin roles | P2 | Member 3 | 2026-10-12 | ✅ Closed | `0c54fde` (PR #1) | 2026-10-12 ✅ |
| BUG-04 | Duplicate login signature requests cause misleading "another wallet" error | P2 | Member 3 | 2026-10-12 | 🔴 Open | — | — |
| KI-01 | MetaMask flags the site as "Malicious" | — (known issue) | Member 2 (informed) | 2026-10-12 | ⚠️ Won't fix | — | — |
| KI-02 | Transactions fail when MetaMask "smart account" (EIP-7702) is enabled | — (known issue / environment) | Member 3 (error message) | 2026-10-12 | ⚠️ Workaround | — | — |

All three defects were found during test-environment setup (before formal execution), fixed by Member 3 in a single PR merged into `feature/backend-member2` at 14:46, and deployed to Render at 15:23 on 2026-10-12.

---

## BUG-01 · Faucet button shows wrong amount

- **Where**: Home page, `frontend/templates/index.html` line 12
- **Observed**: Button read "领取 10,000 测试稳定币" (claim 10,000 test stablecoins).
- **Expected**: `MockStablecoin.FAUCET_AMOUNT` is 100,000 mUSD (verified by an on-chain call on Sepolia); the success toast already said 100,000, so button and toast contradicted each other.
- **Fix**: Button now reads "Claim 100,000 mUSD Test Tokens".
- **Retest**: Live home page shows the corrected label. ✅

## BUG-02 · Stale session state after switching MetaMask account

- **Where**: `frontend/static/js/web3-provider.js` (`accountsChanged` handler); `frontend/templates/register.html` (`checkMyRegistration`)
- **Steps to reproduce**: Log in as CE and submit a registration → switch MetaMask to S1 (not yet signed in) → stay on the registration page.
- **Observed**: The header switched to S1's address, but S1 was never prompted to sign in. The registration status request failed silently (`catch (_) {}`), so the page kept showing CE's "Pending" banner and the submit button stayed disabled. A user could not tell they needed to sign in again.
- **Expected**: After switching accounts, the page clearly prompts the new account to sign in and does not show the previous account's data.
- **Fix**: Header button turns into a prominent "🔑 Sign In (address)" when the session is not authenticated; the registration page resets its status on failure; submitting without a session first requests a signature.
- **Retest**: Switched CE → S1 on the live site; "Sign In" button appeared, and after signing the page showed S1's own state. ✅
- **Related test case**: TC-F01-04 (partial pass before the fix).

## BUG-03 · No UI to grant Auditor / Admin roles

- **Where**: `frontend/templates/admin/system.html`, `frontend/templates/register.html`, `backend/routes/enterprises.py`
- **Observed**: Admins could only approve registration applications, and applications accept only SUPPLIER / CORE_ENTERPRISE / FUNDER (frontend form and backend `VALID_ROLES`). The "Roles & System" page offered only revoke and pause. Granting AUDITOR to the test auditor account required Member 1 to use the command line.
- **Expected**: PRD §2 states roles are granted on-chain by the admin; the auditor role must be grantable through the application.
- **Fix**: New "Direct Grant On-Chain Role" form on the admin page (Auditor, Admin, Supplier, Core Enterprise, Funder), calling `RoleManager.grantRole`.
- **Retest**: Form present on the live admin page. ✅ (Functional grant is exercised in TC-F03 / TC-F04 during formal execution.)

## BUG-04 · Duplicate login signature requests cause misleading "another wallet" error

- **Where**: `frontend/templates/register.html` (calls `ensureAuthenticated()` automatically on load, lines ~79/150/180) together with the header "Sign In" button (`connectWallet` → `authenticateWallet`); backend `backend/routes/auth.py` keeps only the latest challenge in the session.
- **Steps to reproduce**: As F1 (already a Funder, not signed in), open the site → the registration page auto-requests a login signature → also click the header "🔑 Sign In" → confirm the *older* request in MetaMask.
- **Observed**: Toast "Signature was produced by another wallet." The MetaMask request showed the correct wallet (F1) and the active MetaMask account was F1. Repeated clicks queued up to 4 pending requests ("1 of 4").
- **Cause**: Each request creates a new nonce, and the backend session stores only the most recent challenge. Signing an older challenge is verified against the newer message, so the recovered address does not match and the backend returns `ADDRESS_MISMATCH`.
- **Expected**: Only one signature request at a time (ignore or disable "Sign In" while a request is pending); if a stale challenge is signed, show "Login request expired, please sign in again" instead of blaming the wallet.
- **Workaround**: Reject all pending requests, refresh, and confirm only the single latest request.
- **Also observed**: Before signing in, F1 (an approved Funder) was shown the Enterprise Onboarding Application page instead of the funder dashboard — to be re-checked after sign-in.

## KI-01 · MetaMask flags the site as "Malicious" (known issue, won't fix)

- **Observed**: Connecting MetaMask to `supply-chain-finance-dapp-nkkr.onrender.com` shows "Malicious—flagged as unsafe"; signature requests show a red "Review alert". Users can proceed via "Continue at your own risk".
- **Cause (likely)**: MetaMask's phishing detection treating a newly deployed wallet-connecting site on a shared `onrender.com` subdomain as suspicious. The site itself is the team's own deployment.
- **Decision**: Not fixed (team decision, 2026-10-12). Possible remedies — a false-positive dispute to MetaMask or a custom domain — are outside the project's scope.
- **Mitigation**: User-testing participants are briefed beforehand; the demo video explains it in one line; the technical report discusses it as a real-world adoption barrier.

## KI-02 · Transactions fail when MetaMask "smart account" (EIP-7702) is enabled

- **Observed**: F1's first faucet claim (TC-F22-01) failed with an unreadable message: `transaction execution reverted (action="sendTransaction", data=null, reason=null ...)`. Tx [`0x16712e25…bbb5f7ad`](https://sepolia.etherscan.io/tx/0x16712e25346abcfe18a68b4ac1b8272698a132f52481d50b1faab896bbb5f7ad) (block 11897499) was **not** sent to MockStablecoin but to MetaMask's delegation contract `0xdb9b1e94…47db3` as a type-4 (EIP-7702) transaction wrapping `faucet()` inside `redeemDelegations(...)`; it reverted inside that wrapper.
- **Cause**: MetaMask's "Use smart account" toggle was on for Sepolia for F1 and CE, so both addresses had been upgraded to MetaMask smart accounts (on-chain code `0xef0100…`). The other accounts were standard EOAs.
- **Workaround (applied 2026-10-12)**: Account details → Smart account → Sepolia toggle off for F1 and CE; verified on-chain that all 8 test accounts are standard EOAs again (`eth_getCode` = `0x`).
- **Impact / recommendation**: Real users with smart accounts enabled may hit the same failure with an unhelpful error. The frontend could detect a revert without reason and suggest switching to a standard account; the report should mention wallet compatibility as an adoption risk.
