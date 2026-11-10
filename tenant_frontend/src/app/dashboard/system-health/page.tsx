"use client";

import { useEffect, useMemo, useState } from "react";
import {
    Activity,
    CheckCircle2,
    Database,
    HardDrive,
    Info,
    Mail,
    RefreshCw,
    Timer,
    Workflow,
    XCircle,
    AlertTriangle,
    Server,
    Zap,
    Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TableShell } from "@/components/common/table/TableShell";
import { FilterBar } from "@/components/common/table/FilterBar";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { EmptyState } from "@/components/feedback/EmptyState";
import Unauthorized from "@/components/Unauthorized";
import { useSystemHealth } from "@/hooks/useSystemHealth";
import { usePermissions } from "@/providers/PermissionProvider";
import { EndpointTiming, ServiceStatus, SystemHealth } from "@/types/SystemHealth";
import {
    bucketRange,
    formatMs,
    MIN_SAMPLE,
    rating,
    RatingKind,
    selectEndpoints,
    SLOW_P95_MS,
    SortKey,
    ViewFilter,
} from "@/lib/systemHealth";

const STATUS_CONFIG: Record<ServiceStatus, { label: string; badge: string; border: string; dot: string }> = {
    ok: {
        label: "Healthy",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
        border: "border-emerald-200/80 dark:border-emerald-900/60",
        dot: "bg-emerald-500",
    },
    warning: {
        label: "Degraded",
        badge: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
        border: "border-amber-200/80 dark:border-amber-900/60",
        dot: "bg-amber-500",
    },
    down: {
        label: "Failing",
        badge: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
        border: "border-rose-200/80 dark:border-rose-900/60",
        dot: "bg-rose-500",
    },
};

const METHOD_BADGES: Record<string, string> = {
    GET: "bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300",
    POST: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
    PUT: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
    PATCH: "bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-950/60 dark:text-indigo-300",
    DELETE: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
};

const PAGE_SIZE = 25;

function ago(iso: string | null | undefined, now: number): string {
    if (!iso) return "never";
    const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
    return `${Math.round(seconds / 3600)}h ago`;
}

const RATING_BADGE: Record<RatingKind, string> = {
    low: "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400",
    erroring: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
    fast: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
    normal: "bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300",
    moderate: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
    slow: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
};

function ServiceCard({
    icon: Icon,
    title,
    status,
    detail,
    subDetail,
    symptom,
}: {
    icon: typeof Database;
    title: string;
    status: ServiceStatus;
    detail: string;
    subDetail?: string;
    /** What was observed when the service is not healthy (never a guessed cause). */
    symptom?: string;
}) {
    const cfg = STATUS_CONFIG[status];
    return (
        <div className={`rounded-2xl border p-5 flex flex-col justify-between shadow-sm ${cfg.border} bg-white dark:bg-slate-900`}>
            <div>
                <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 text-slate-700 dark:text-slate-300">
                            <Icon className="h-4 w-4" />
                        </div>
                        <span className="font-semibold text-sm text-slate-900 dark:text-white">{title}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className={`inline-flex rounded-full h-2 w-2 ${cfg.dot}`} aria-hidden="true" />
                        <StatusBadge label={cfg.label} className={`border text-[10px] font-medium ${cfg.badge}`} />
                    </div>
                </div>
                <p className="text-base font-bold text-slate-900 dark:text-white">{detail}</p>
                {subDetail && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{subDetail}</p>}
            </div>
            {symptom && status !== "ok" && (
                <div
                    className={`mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs font-medium ${
                        status === "down" ? "text-rose-600 dark:text-rose-400" : "text-amber-700 dark:text-amber-400"
                    }`}
                >
                    {symptom}
                </div>
            )}
        </div>
    );
}

function Tile({ label, value, hint, icon: Icon }: { label: string; value: string; hint: string; icon: typeof Activity }) {
    return (
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</span>
                <Icon className="h-4 w-4 text-slate-400" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{hint}</div>
        </div>
    );
}

function overall(data: SystemHealth): ServiceStatus {
    const statuses = Object.values(data.services)
        .filter(Boolean)
        .map((s) => s!.status);
    if (statuses.includes("down")) return "down";
    if (statuses.includes("warning")) return "warning";
    return "ok";
}

const BANNER: Record<"platform" | "school", Record<ServiceStatus, { title: string; text: string }>> = {
    platform: {
        ok: { title: "All services healthy", text: "The database, cache, background workers and email queue answered their checks." },
        warning: { title: "A service is degraded", text: "A service answered but showed a problem. See the cards below for what was observed." },
        down: { title: "A service is failing", text: "At least one service did not answer its check. See the cards below for what was observed." },
    },
    school: {
        ok: { title: "Your school's services are healthy", text: "Emails are going out and the timings below cover your school's use of the app." },
        warning: { title: "Something needs attention", text: "See the email card below for what was observed." },
        down: { title: "A service is failing", text: "See the email card below for what was observed." },
    },
};
const BANNER_ICON: Record<ServiceStatus, typeof CheckCircle2> = { ok: CheckCircle2, warning: AlertTriangle, down: XCircle };
const BANNER_TONE: Record<ServiceStatus, string> = {
    ok: "bg-emerald-50/80 text-emerald-900 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-200 dark:border-emerald-900",
    warning: "bg-amber-50/80 text-amber-900 border-amber-200 dark:bg-amber-950/30 dark:text-amber-200 dark:border-amber-900",
    down: "bg-rose-50/80 text-rose-900 border-rose-200 dark:bg-rose-950/30 dark:text-rose-200 dark:border-rose-900",
};

function emailSymptom(email: SystemHealth["services"]["email_queue"]): string | undefined {
    if (email.waiting === undefined) return "The email queue could not be read.";
    const parts: string[] = [];
    if (email.failed_24h) parts.push(`${email.failed_24h} email${email.failed_24h === 1 ? "" : "s"} could not be delivered in the last 24 hours`);
    if (email.waiting >= 100) parts.push(`${email.waiting} emails are waiting to be sent`);
    return parts.length ? `${parts.join("; ")}.` : undefined;
}

function EndpointTable({ endpoints }: { endpoints: EndpointTiming[] }) {
    const [search, setSearch] = useState("");
    const [view, setView] = useState<ViewFilter>("all");
    const [sort, setSort] = useState<SortKey>("errors");
    const [page, setPage] = useState(1);

    const rows = useMemo(() => selectEndpoints(endpoints, search, view, sort), [endpoints, search, view, sort]);

    useEffect(() => setPage(1), [search, view, sort]);
    const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    const filtered = search.trim() !== "" || view !== "all";

    return (
        <div className="space-y-3">
            <FilterBar
                searchValue={search}
                onSearchChange={setSearch}
                searchPlaceholder="Search endpoints, e.g. /api/fees/"
                searchAriaLabel="Search endpoints"
                hasActiveFilters={filtered}
                onReset={() => {
                    setSearch("");
                    setView("all");
                }}
            >
                <Select value={view} onValueChange={(v) => setView(v as ViewFilter)}>
                    <SelectTrigger className="h-9 w-full sm:w-44 text-xs" aria-label="Show">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All endpoints</SelectItem>
                        <SelectItem value="errors">With server errors</SelectItem>
                        <SelectItem value="slow">Slow (95% over {SLOW_P95_MS} ms)</SelectItem>
                    </SelectContent>
                </Select>
                <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
                    <SelectTrigger className="h-9 w-full sm:w-48 text-xs" aria-label="Sort by">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="errors">Most server errors first</SelectItem>
                        <SelectItem value="p95">Slowest first</SelectItem>
                        <SelectItem value="requests">Most requests first</SelectItem>
                    </SelectContent>
                </Select>
            </FilterBar>

            {rows.length === 0 ? (
                <EmptyState
                    title="No endpoints match"
                    description={view === "errors" ? "No endpoint answered a server error in the last 24 hours." : "Try another search or filter."}
                    className="py-10 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800"
                />
            ) : (
                <TableShell
                    footer={
                        rows.length > PAGE_SIZE ? (
                            <Pagination page={page} pageSize={PAGE_SIZE} count={rows.length} onPageChange={setPage} className="border-t border-slate-100 dark:border-slate-800 px-4 py-3" />
                        ) : undefined
                    }
                >
                    <div className="max-h-144 overflow-y-auto">
                        <Table className="min-w-184">
                            <TableHeader className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900 shadow-[0_1px_0_0] shadow-slate-200 dark:shadow-slate-800">
                                <TableRow>
                                    <TableHead className="font-semibold text-xs">Method & endpoint</TableHead>
                                    <TableHead className="w-24 text-right font-semibold text-xs">Requests</TableHead>
                                    <TableHead className="w-32 text-right font-semibold text-xs" title="The time range the middle request fell in">
                                        Typical (p50)
                                    </TableHead>
                                    <TableHead className="w-32 text-right font-semibold text-xs" title="The time range 95% of requests finished within">
                                        Slowest 5% (p95)
                                    </TableHead>
                                    <TableHead className="w-24 text-right font-semibold text-xs">Server errors</TableHead>
                                    <TableHead className="w-28 text-center font-semibold text-xs">Rating</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {shown.map((r) => {
                                    const ev = rating(r);
                                    const evBadge = RATING_BADGE[ev.kind];
                                    const methodBadge = METHOD_BADGES[r.method] ?? "bg-slate-100 text-slate-700";
                                    return (
                                        <TableRow key={`${r.method} ${r.endpoint}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                            <TableCell>
                                                <div className="flex items-center gap-2 font-mono text-xs">
                                                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 font-bold ${methodBadge}`}>
                                                        {r.method}
                                                    </Badge>
                                                    <span className="text-slate-800 dark:text-slate-200 font-medium truncate max-w-md" title={r.endpoint}>
                                                        {r.endpoint}
                                                    </span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                                {r.requests.toLocaleString("en-IN")}
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300 whitespace-nowrap">
                                                {bucketRange(r.p50_ms)}
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300 whitespace-nowrap">
                                                {r.requests < MIN_SAMPLE ? (
                                                    <span className="text-slate-400" title={`Needs at least ${MIN_SAMPLE} requests`}>—</span>
                                                ) : (
                                                    bucketRange(r.p95_ms)
                                                )}
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs">
                                                {r.server_errors > 0 ? (
                                                    <span className="text-rose-600 dark:text-rose-400 font-bold">{r.server_errors}</span>
                                                ) : (
                                                    <span className="text-slate-400">0</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <span title={ev.title}>
                                                    <StatusBadge label={ev.label} className={`border text-[10px] font-medium ${evBadge}`} />
                                                </span>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>
                </TableShell>
            )}
            <p className="text-xs text-slate-500 dark:text-slate-400">
                Showing {shown.length} of {rows.length} endpoint{rows.length === 1 ? "" : "s"}
                {filtered ? ` (${endpoints.length} in total)` : ""}.
            </p>
        </div>
    );
}

export default function SystemHealthPage() {
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch, isFetching } = useSystemHealth();
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 5_000);
        return () => clearInterval(timer);
    }, []);

    if (!can("view_system_health")) return <Unauthorized />;

    const header = (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-slate-800 pb-5">
            <div>
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-sky-600 text-white shadow-sm">
                        <Activity className="h-5 w-5" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">System Health</h1>
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {data?.platform
                        ? "Shared services, this school's email queue, and this school's API response times."
                        : "Your school's email queue and how quickly the app has been answering your school's requests."}
                </p>
            </div>

            <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="shrink-0 h-9 font-medium text-xs bg-white dark:bg-slate-800 shadow-sm"
            >
                <RefreshCw className={`h-3.5 w-3.5 mr-2 ${isFetching ? "animate-spin text-sky-600" : "text-slate-500"}`} />
                {isFetching ? "Checking..." : "Check again"}
            </Button>
        </div>
    );

    if (isLoading) {
        return (
            <div className="space-y-6 max-w-6xl">
                {header}
                <LoadingState className="py-20" />
            </div>
        );
    }

    if (isError || !data) {
        return (
            <div className="space-y-6 max-w-6xl">
                {header}
                <ErrorState onRetry={refetch} />
            </div>
        );
    }

    const state = overall(data);
    const banner = BANNER[data.platform ? "platform" : "school"][state];
    const BannerIcon = BANNER_ICON[state];
    const { database, cache, background_jobs: jobs, email_queue: email } = data.services;
    const api = data.api;
    const errorRate = api && api.requests ? (api.server_errors / api.requests) * 100 : 0;
    const enoughSamples = !!api && api.requests >= MIN_SAMPLE;

    return (
        <div className="space-y-6 max-w-6xl">
            {header}

            <div className={`flex items-start gap-3.5 p-4 rounded-2xl border ${BANNER_TONE[state]}`} role="status">
                <BannerIcon className="h-5 w-5 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h2 className="text-xs font-bold uppercase tracking-wider">{banner.title}</h2>
                        <span className="text-[11px] opacity-75 shrink-0 flex items-center gap-1 font-mono">
                            <Clock className="h-3 w-3" /> Checked {ago(data.checked_at, now)}
                        </span>
                    </div>
                    <p className="text-xs mt-0.5 leading-relaxed opacity-90">{banner.text}</p>
                </div>
            </div>

            <div className={`grid gap-4 sm:grid-cols-2 ${data.platform ? "xl:grid-cols-4" : ""}`}>
                {database && (
                    <ServiceCard
                        icon={Database}
                        title="Database"
                        status={database.status}
                        detail={database.status === "ok" ? `Answered in ${formatMs(database.ms)}` : "No answer"}
                        subDetail="A test query to PostgreSQL"
                        symptom="The database did not answer a test query."
                    />
                )}
                {cache && (
                    <ServiceCard
                        icon={HardDrive}
                        title="Cache (Redis)"
                        status={cache.status}
                        detail={cache.status === "ok" ? `Answered in ${formatMs(cache.ms)}` : "No answer"}
                        subDetail="A test write and read"
                        symptom="The cache did not answer a test write and read."
                    />
                )}
                {jobs && (
                    <ServiceCard
                        icon={Workflow}
                        title="Background workers"
                        status={jobs.status}
                        detail={
                            jobs.status === "ok"
                                ? `Last heartbeat ${ago(jobs.last_seen, now)}`
                                : jobs.last_seen
                                ? `Last heartbeat ${ago(jobs.last_seen, now)}`
                                : "No heartbeat received"
                        }
                        subDetail="Celery worker and scheduler, expected every minute"
                        symptom="No heartbeat in the last 3 minutes: scheduled jobs and queued emails are not being processed."
                    />
                )}
                <ServiceCard
                    icon={Mail}
                    title="Email queue"
                    status={email.status}
                    detail={email.waiting === undefined ? "Queue unavailable" : `${email.waiting} waiting · ${email.sent_24h ?? 0} sent in 24h`}
                    subDetail={email.failed_24h ? `${email.failed_24h} not delivered in 24h` : "No failed deliveries in 24h"}
                    symptom={emailSymptom(email)}
                />
            </div>

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-slate-200/80 dark:border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                        <Zap className="h-5 w-5 text-sky-600" />
                        <h2 className="text-base font-bold text-slate-900 dark:text-white">API response times (last 24 hours)</h2>
                    </div>
                    <p className="text-xs text-slate-500">This school&apos;s requests only</p>
                </div>

                {!api ? (
                    <EmptyState
                        title="Response times are not available"
                        description="The timings could not be read just now. Try again in a moment."
                        className="py-12 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800"
                    />
                ) : api.requests === 0 ? (
                    <EmptyState
                        title="No requests recorded in the last 24 hours"
                        description="Timings appear here as people use the app."
                        className="py-12 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800"
                    />
                ) : (
                    <>
                        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                            <Tile icon={Activity} label="Requests" value={api.requests.toLocaleString("en-IN")} hint="Answered in the last 24 hours" />
                            <Tile
                                icon={Timer}
                                label="Typical (p50)"
                                value={bucketRange(api.p50_ms)}
                                hint="Half of all requests finished within this range"
                            />
                            <Tile
                                icon={Clock}
                                label="Slowest 5% (p95)"
                                value={enoughSamples ? bucketRange(api.p95_ms) : "—"}
                                hint={
                                    !enoughSamples
                                        ? `Shown after ${MIN_SAMPLE} requests`
                                        : api.p95_ms !== null && api.p95_ms <= SLOW_P95_MS
                                        ? "95% of requests finished within this range"
                                        : `5% of requests took longer than ${formatMs(SLOW_P95_MS)}`
                                }
                            />
                            <Tile
                                icon={AlertTriangle}
                                label="Server errors"
                                value={api.server_errors.toLocaleString("en-IN")}
                                hint={api.server_errors ? `${errorRate.toFixed(2)}% of requests failed with a 5xx` : "No request failed with a 5xx"}
                            />
                        </div>

                        <div className="flex items-start gap-2 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/60 p-3 text-xs text-slate-600 dark:text-slate-400">
                            <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                            <p>
                                Times are counted in ranges (under 25 ms, 25–50 ms, … 1.6–3.2 s, over 3.2 s), so p50 and p95 show the
                                range that holds the middle request and the 95th-percentile request, not an exact time.
                            </p>
                        </div>

                        <div className="space-y-3">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <Server className="h-4 w-4 text-slate-500" />
                                <span>By endpoint</span>
                            </h3>
                            <EndpointTable endpoints={api.endpoints} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
