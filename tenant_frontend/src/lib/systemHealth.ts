/**
 * Pure helpers for the System Health page (no imports, so `node --test` can load this file directly).
 *
 * The backend counts each request into a timing range (core/request_metrics.py); p50/p95 are the upper limit of
 * the range holding the median / 95th-percentile request. They are shown as ranges, never as exact times.
 */

export interface EndpointRow {
    endpoint: string;
    method: string;
    requests: number;
    p50_ms: number | null;
    p95_ms: number | null;
    server_errors: number;
}

/** Upper limits (ms) of the timing ranges; must match BUCKETS_MS in backend/core/request_metrics.py. */
export const BUCKETS_MS = [25, 50, 100, 200, 400, 800, 1600, 3200];
export const MIN_SAMPLE = 20;
export const SLOW_P95_MS = 800;
export const ERRORING_SHARE = 0.05;

/** An exact measured time, e.g. a database ping: 1600 -> "1.6 s", 40 -> "40 ms". */
export function formatMs(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "—";
    return ms >= 1000 ? `${+(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

/** A p50/p95 value as its range: 800 -> "400–800 ms", 25 -> "under 25 ms", null -> "over 3.2 s". */
export function bucketRange(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "over 3.2 s";
    const index = BUCKETS_MS.indexOf(ms);
    if (index === 0) return `under ${formatMs(ms)}`;
    if (index < 0) return `up to ${formatMs(ms)}`;
    const lower = BUCKETS_MS[index - 1];
    if (ms >= 1000) return `${+(lower / 1000).toFixed(2)}–${formatMs(ms)}`;
    return `${lower}–${formatMs(ms)}`;
}

export function isErroring(r: EndpointRow): boolean {
    return r.requests >= MIN_SAMPLE && r.server_errors / r.requests >= ERRORING_SHARE;
}

export function isSlow(r: EndpointRow): boolean {
    return r.requests >= MIN_SAMPLE && (r.p95_ms === null || r.p95_ms > SLOW_P95_MS);
}

export type RatingKind = "low" | "erroring" | "fast" | "normal" | "moderate" | "slow";

/** Errors come first (a request that fails quickly is not "Fast"), then speed. */
export function rating(r: EndpointRow): { kind: RatingKind; label: string; title?: string } {
    if (r.requests < MIN_SAMPLE) return { kind: "low", label: "Low sample", title: `Needs at least ${MIN_SAMPLE} requests to rate` };
    if (isErroring(r)) {
        const share = Math.round((r.server_errors / r.requests) * 100);
        return { kind: "erroring", label: "Erroring", title: `${share}% of requests failed with a server error` };
    }
    const { p50_ms: p50, p95_ms: p95 } = r;
    if (p50 !== null && p50 <= 200 && p95 !== null && p95 <= 1600) return { kind: "fast", label: "Fast" };
    if (p50 !== null && p50 <= 400 && p95 !== null && p95 <= 3200) return { kind: "normal", label: "Normal" };
    if (p50 !== null && p50 <= 800) return { kind: "moderate", label: "Moderate" };
    return { kind: "slow", label: "Slow" };
}

export type ViewFilter = "all" | "errors" | "slow";
export type SortKey = "errors" | "p95" | "requests";

/** The rows to show: searched (method + path), filtered, then sorted. Never changes the input array. */
export function selectEndpoints<T extends EndpointRow>(rows: T[], search: string, view: ViewFilter, sort: SortKey): T[] {
    const term = search.trim().toLowerCase();
    const p95Rank = (r: EndpointRow) => (r.p95_ms === null ? Number.MAX_SAFE_INTEGER : r.p95_ms);
    return rows
        .filter((r) => !term || `${r.method} ${r.endpoint}`.toLowerCase().includes(term))
        .filter((r) => (view === "errors" ? r.server_errors > 0 : view === "slow" ? isSlow(r) : true))
        .sort((a, b) => {
            if (sort === "errors") return b.server_errors - a.server_errors || p95Rank(b) - p95Rank(a) || b.requests - a.requests;
            if (sort === "p95") return p95Rank(b) - p95Rank(a) || b.requests - a.requests;
            return b.requests - a.requests;
        });
}
