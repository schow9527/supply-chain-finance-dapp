const test = require("node:test");
const assert = require("node:assert");
const ApiClient = require("../static/js/api-client.js");

test("ApiClient - Request generation and error handling", async () => {
    let lastUrl = null;
    let lastOptions = null;

    const client = new ApiClient("http://127.0.0.1:5000");
    // Inject mock fetch implementation
    client.customFetch = async (url, options) => {
        lastUrl = url;
        lastOptions = options;
        return {
            ok: true,
            status: 200,
            json: async () => ({ status: "ok" })
        };
    };

    // Test getMe
    await client.getMe();
    assert.strictEqual(lastUrl, "http://127.0.0.1:5000/api/me");
    assert.strictEqual(lastOptions.credentials, "include");

    await client.requestNonce("0x1234567890123456789012345678901234567890");
    assert.strictEqual(lastUrl, "http://127.0.0.1:5000/api/auth/nonce");
    assert.strictEqual(lastOptions.credentials, "include");

    // Test registerEnterprise
    await client.registerEnterprise({ name: "NTU Corp", role: "SUPPLIER" });
    assert.strictEqual(lastUrl, "http://127.0.0.1:5000/api/enterprises");
    assert.strictEqual(lastOptions.method, "POST");

    // Test getInvoices with params
    await client.getInvoices({ supplier: "0x123", status: "PENDING" });
    assert.match(lastUrl, /\/api\/invoices\?supplier=0x123&status=PENDING/);

    // Test getReceivableHistory
    await client.getReceivableHistory(42);
    assert.strictEqual(lastUrl, "http://127.0.0.1:5000/api/receivables/42/history");

    // Test Unified Error Format handling per PRD section 7
    client.customFetch = async () => ({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({
            error: {
                code: "INVALID_INVOICE_AMOUNT",
                message: "Invoice amount must be positive"
            }
        })
    });

    await assert.rejects(async () => {
        await client.getInvoice(999);
    }, (err) => {
        assert.strictEqual(err.code, "INVALID_INVOICE_AMOUNT");
        assert.strictEqual(err.message, "Invoice amount must be positive");
        assert.strictEqual(err.status, 400);
        return true;
    });
});
