/** Upload-first invoice flow shared by the browser and Node tests. */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.InvoiceUploadFlow = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {
    async function uploadAndSubmit({ apiClient, contractClient, formData, expectedHash,
                                     invoiceNo, buyer, amount, dueDate }) {
        const uploaded = await apiClient.uploadInvoiceFile(formData);
        if (!uploaded.file_hash || uploaded.file_hash.toLowerCase() !== expectedHash.toLowerCase()) {
            const error = new Error("Uploaded PDF hash does not match the browser hash");
            error.code = "FILE_HASH_MISMATCH";
            throw error;
        }
        await contractClient.submitInvoice(
            invoiceNo, buyer, amount, dueDate, uploaded.file_hash
        );
        return uploaded;
    }

    return { uploadAndSubmit };
}));
