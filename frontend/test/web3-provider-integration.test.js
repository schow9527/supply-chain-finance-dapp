const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(
    path.join(__dirname, "..", "static", "js", "web3-provider.js"),
    "utf8"
);
const apiSource = fs.readFileSync(
    path.join(__dirname, "..", "static", "js", "api-client.js"),
    "utf8"
);

test("MPA reconnect is silent and explicit connect performs wallet authentication", () => {
    const init = source.slice(source.indexOf("async function initWeb3"), source.indexOf("async function connectWallet"));
    const connect = source.slice(source.indexOf("async function connectWallet"), source.indexOf("async function handleAccountsChanged"));

    assert.match(init, /eth_accounts/);
    assert.doesNotMatch(init, /authenticateWallet\(\)/);
    assert.match(connect, /eth_requestAccounts/);
    assert.match(connect, /authenticateWallet\(\)/);
    assert.match(source, /requestNonce\(account\)/);
    assert.match(source, /signMessage\(challenge\.message\)/);
    assert.match(source, /verifySignature\(account, signature\)/);
});

test("role lookup uses bytes32 hashes and account changes revoke the old session", () => {
    for (const role of ["SUPPLIER", "CORE_ENTERPRISE", "FUNDER", "AUDITOR"]) {
        assert.match(source, new RegExp(`toUtf8Bytes\\("${role}"\\)`));
    }
    assert.match(source, /0x0{64}/);
    assert.match(source, /accountsChanged[\s\S]*apiClient\.logout\(\)/);
    assert.match(apiSource, /credentials:\s*"include"/);
});

test("deleted demo role switcher is not restored", () => {
    assert.doesNotMatch(source, /renderDemoSwitcher|simulateRole|demo-switcher/);
});
