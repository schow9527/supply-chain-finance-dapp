const test = require("node:test");
const assert = require("node:assert");
const InvoiceUploadFlow = require("../static/js/invoice-upload-flow.js");

const args = {
    formData: {},
    expectedHash: "0x" + "a".repeat(64),
    invoiceNo: "INV-1",
    buyer: "0x2222222222222222222222222222222222222222",
    amount: "1000000",
    dueDate: 2000000000
};

test("invoice upload failure never calls the contract", async () => {
    let contractCalls = 0;
    const apiClient = { uploadInvoiceFile: async () => { throw new Error("offline"); } };
    const contractClient = { submitInvoice: async () => { contractCalls += 1; } };
    await assert.rejects(
        InvoiceUploadFlow.uploadAndSubmit({ ...args, apiClient, contractClient }),
        /offline/
    );
    assert.strictEqual(contractCalls, 0);
});

test("hash mismatch never calls the contract", async () => {
    let contractCalls = 0;
    const apiClient = { uploadInvoiceFile: async () => ({ file_hash: "0x" + "b".repeat(64) }) };
    const contractClient = { submitInvoice: async () => { contractCalls += 1; } };
    await assert.rejects(
        InvoiceUploadFlow.uploadAndSubmit({ ...args, apiClient, contractClient }),
        error => error.code === "FILE_HASH_MISMATCH"
    );
    assert.strictEqual(contractCalls, 0);
});

test("successful upload uses the backend file hash", async () => {
    const calls = [];
    const apiClient = { uploadInvoiceFile: async () => ({ file_hash: args.expectedHash }) };
    const contractClient = { submitInvoice: async (...values) => { calls.push(values); } };
    await InvoiceUploadFlow.uploadAndSubmit({ ...args, apiClient, contractClient });
    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0][4], args.expectedHash);
});
