/**
 * REST API Client for Supply Chain Finance DApp Backend (Flask)
 * Supports browser and Node.js testing.
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.ApiClient = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {

    class ApiClient {
        constructor(baseUrl = "") {
            this.baseUrl = baseUrl;
        }

        async _request(endpoint, options = {}) {
            const url = `${this.baseUrl}${endpoint}`;
            const headers = options.headers || {};
            if (!(options.body instanceof (typeof FormData !== "undefined" ? FormData : Object))) {
                headers["Content-Type"] = headers["Content-Type"] || "application/json";
            }

            const fetchFn = this.customFetch || (typeof fetch !== "undefined" ? fetch : null);
            if (!fetchFn) {
                throw new Error("No fetch implementation available");
            }

            const response = await fetchFn(url, {
                ...options,
                credentials: "include",
                headers
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const errCode = (data.error && data.error.code) || "HTTP_ERROR";
                const errMsg = (data.error && data.error.message) || response.statusText || "Request failed";
                const error = new Error(errMsg);
                error.code = errCode;
                error.status = response.status;
                throw error;
            }

            return data;
        }

        // F-01: Get user profile and on-chain role
        async requestNonce(walletAddress) {
            return this._request("/api/auth/nonce", {
                method: "POST",
                body: JSON.stringify({ wallet_address: walletAddress })
            });
        }

        async verifySignature(walletAddress, signature) {
            return this._request("/api/auth/verify", {
                method: "POST",
                body: JSON.stringify({ wallet_address: walletAddress, signature })
            });
        }

        async logout() {
            return this._request("/api/auth/logout", { method: "POST" });
        }

        async getMe() {
            return this._request("/api/me");
        }

        // F-02: Submit enterprise registration
        async registerEnterprise(data) {
            return this._request("/api/enterprises", {
                method: "POST",
                body: JSON.stringify(data)
            });
        }

        // F-03: Admin list enterprise applications
        async getEnterprises(status = "") {
            const query = status ? `?status=${encodeURIComponent(status)}` : "";
            return this._request(`/api/enterprises${query}`);
        }

        // F-03: Admin review enterprise application
        async reviewEnterprise(id, data) {
            return this._request(`/api/enterprises/${id}`, {
                method: "PATCH",
                body: JSON.stringify(data)
            });
        }

        // F-06: Upload invoice PDF, returns sha256 file_hash
        async uploadInvoiceFile(formData) {
            return this._request("/api/invoices/file", {
                method: "POST",
                body: formData
            });
        }

        // F-10: Get invoices list with optional address and status
        async getInvoices(params = {}) {
            const qs = new URLSearchParams(params).toString();
            return this._request(`/api/invoices${qs ? "?" + qs : ""}`);
        }

        // F-10: Get single invoice details
        async getInvoice(id) {
            return this._request(`/api/invoices/${id}`);
        }

        // F-11: Get holding receivables for address
        async getReceivables(holder) {
            return this._request(`/api/receivables?holder=${encodeURIComponent(holder)}`);
        }

        // F-14: Get receivable lifecycle history
        async getReceivableHistory(id) {
            return this._request(`/api/receivables/${id}/history`);
        }

        // F-16: Get financing requests
        async getFinancingRequests(status = "") {
            const query = status ? `?status=${encodeURIComponent(status)}` : "";
            return this._request(`/api/financing${query}`);
        }

        // F-16, F-17: Get financing request detail with all quotes
        async getFinancingDetail(id) {
            return this._request(`/api/financing/${id}`);
        }

        // F-23: Get dashboard aggregation statistics for address
        async getDashboard(address) {
            return this._request(`/api/dashboard?address=${encodeURIComponent(address)}`);
        }

        // F-24: Get transaction history for address
        async getTransactions(address) {
            return this._request(`/api/transactions?address=${encodeURIComponent(address)}`);
        }

        // F-25: Get contract event logs with filters
        async getEvents(params = {}) {
            const qs = new URLSearchParams(params).toString();
            return this._request(`/api/events${qs ? "?" + qs : ""}`);
        }
    }

    return ApiClient;
}));
