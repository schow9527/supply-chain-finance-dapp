/**
 * Small Chart.js wrapper for the role dashboards (F-23 data visualisation).
 * Re-rendering the same canvas destroys the previous chart first.
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.DashboardCharts = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {
    const PALETTE = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#6b7280"];
    const charts = {};

    // Convert a 6-decimal mUSD unit string/bigint into a plain number for charting
    function toTokens(units) {
        return Number(BigInt(units || 0)) / 1e6;
    }

    function render(canvasId, type, labels, values) {
        if (typeof document === "undefined" || typeof Chart === "undefined") return;
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        if (charts[canvasId]) charts[canvasId].destroy();
        charts[canvasId] = new Chart(canvas, {
            type,
            data: { labels, datasets: [{ data: values, backgroundColor: PALETTE.slice(0, values.length) }] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: type !== "bar", position: "bottom" } }
            }
        });
    }

    return { render, toTokens };
}));
