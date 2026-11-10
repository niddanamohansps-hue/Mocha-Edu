import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
    BUCKETS_MS,
    bucketRange,
    formatMs,
    isSlow,
    rating,
    selectEndpoints,
} from "../src/lib/systemHealth.ts";

const row = (over = {}) => ({
    endpoint: "/api/things/",
    method: "GET",
    requests: 100,
    p50_ms: 100,
    p95_ms: 400,
    server_errors: 0,
    ...over,
});

describe("System Health: latency ranges", () => {
    it("shows a percentile as the range it stands for, never as an exact time", () => {
        assert.equal(bucketRange(25), "under 25 ms");
        assert.equal(bucketRange(800), "400–800 ms");
        assert.equal(bucketRange(1600), "0.8–1.6 s");
        assert.equal(bucketRange(3200), "1.6–3.2 s");
        assert.equal(bucketRange(null), "over 3.2 s");
    });

    it("keeps the same ranges as the backend", () => {
        const backend = fs.readFileSync(path.resolve(import.meta.dirname, "../../backend/core/request_metrics.py"), "utf8");
        const match = backend.match(/BUCKETS_MS = \(([^)]*)\)/);
        assert.ok(match, "BUCKETS_MS not found in request_metrics.py");
        assert.deepEqual(match[1].split(",").map((v) => Number(v.trim())), BUCKETS_MS);
    });

    it("formats exact measurements such as a ping", () => {
        assert.equal(formatMs(3), "3 ms");
        assert.equal(formatMs(1600), "1.6 s");
        assert.equal(formatMs(null), "—");
    });
});

describe("System Health: ratings", () => {
    it("rates an endpoint that often fails as Erroring, however fast it is", () => {
        assert.equal(rating(row({ requests: 21, server_errors: 16, p50_ms: 25, p95_ms: 50 })).kind, "erroring");
        assert.equal(rating(row({ requests: 100, server_errors: 4 })).kind, "fast"); // under 5% is not erroring
    });

    it("does not rate a small sample", () => {
        assert.equal(rating(row({ requests: 5, server_errors: 5 })).kind, "low");
    });

    it("rates speed from the ranges", () => {
        assert.equal(rating(row({ p50_ms: 200, p95_ms: 1600 })).kind, "fast");
        assert.equal(rating(row({ p50_ms: 400, p95_ms: 3200 })).kind, "normal");
        assert.equal(rating(row({ p50_ms: 800, p95_ms: null })).kind, "moderate");
        assert.equal(rating(row({ p50_ms: 1600, p95_ms: null })).kind, "slow");
        assert.equal(isSlow(row({ p95_ms: null })), true);
        assert.equal(isSlow(row({ p95_ms: 800 })), false);
    });
});

describe("System Health: search, filters and sorting", () => {
    const rows = [
        row({ endpoint: "/api/fees/dues/", requests: 50, p95_ms: 800 }),
        row({ endpoint: "/api/academics/assignments/", requests: 457, p95_ms: 3200, server_errors: 35 }),
        row({ endpoint: "/api/auth/login/", method: "POST", requests: 33, p95_ms: null }),
        row({ endpoint: "/api/students/", requests: 9, p95_ms: null }),
    ];

    it("searches method and path", () => {
        assert.deepEqual(selectEndpoints(rows, "post", "all", "requests").map((r) => r.endpoint), ["/api/auth/login/"]);
        assert.deepEqual(selectEndpoints(rows, "FEES", "all", "requests").map((r) => r.endpoint), ["/api/fees/dues/"]);
    });

    it("filters to errors or to slow endpoints (with enough requests)", () => {
        assert.deepEqual(selectEndpoints(rows, "", "errors", "errors").map((r) => r.endpoint), ["/api/academics/assignments/"]);
        assert.deepEqual(
            selectEndpoints(rows, "", "slow", "p95").map((r) => r.endpoint),
            ["/api/auth/login/", "/api/academics/assignments/"],
        );
    });

    it("sorts by errors, then slowness; by slowness; or by volume", () => {
        assert.equal(selectEndpoints(rows, "", "all", "errors")[0].endpoint, "/api/academics/assignments/");
        assert.equal(selectEndpoints(rows, "", "all", "p95")[0].p95_ms, null);
        assert.equal(selectEndpoints(rows, "", "all", "requests")[0].requests, 457);
    });

    it("does not change the rows it is given", () => {
        const before = rows.map((r) => r.endpoint);
        selectEndpoints(rows, "", "all", "p95");
        assert.deepEqual(rows.map((r) => r.endpoint), before);
    });
});
