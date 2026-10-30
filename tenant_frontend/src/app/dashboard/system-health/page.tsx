"use client";

import { useEffect, useState } from "react";
import {
    Activity,
    CheckCircle2,
    Database,
    HardDrive,
    Mail,
    RefreshCw,
    Timer,
    Workflow,
    XCircle,
    AlertTriangle,
    ShieldCheck,
    Cpu,
    Server,
    Zap,
    Radio,
    Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TableShell } from "@/components/common/table/TableShell";
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
import { ServiceStatus, SystemHealth } from "@/types/SystemHealth";

const STATUS_CONFIG: Record<
    ServiceStatus,
    { label: string; badge: string; border: string; bg: string; dot: string; text: string }
> = {
    ok: {
        label: "Operational",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
        border: "border-emerald-200/80 dark:border-emerald-900/60",
        bg: "bg-emerald-50/40 dark:bg-emerald-950/20",
        dot: "bg-emerald-500",
        text: "text-emerald-700 dark:text-emerald-400",
    },
    warning: {
        label: "Degraded",
        badge: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
        border: "border-amber-200/80 dark:border-amber-900/60",
        bg: "bg-amber-50/40 dark:bg-amber-950/20",
        dot: "bg-amber-500",
        text: "text-amber-700 dark:text-amber-400",
    },
    down: {
        label: "Offline",
        badge: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
        border: "border-rose-200/80 dark:border-rose-900/60",
        bg: "bg-rose-50/40 dark:bg-rose-950/20",
        dot: "bg-rose-500",
        text: "text-rose-700 dark:text-rose-400",
    },
};

const METHOD_BADGES: Record<string, string> = {
    GET: "bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300",
    POST: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
    PUT: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
    PATCH: "bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-950/60 dark:text-indigo-300",
    DELETE: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
};

/** 1600 -> "1.6 s", 40 -> "40 ms", null -> "over 3.2 s" (slower than slowest bucket). */
function formatMs(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "over 3.2 s";
    return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

function ago(iso: string | null, now: number): string {
    if (!iso) return "never";
    const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
    return `${Math.round(seconds / 3600)}h ago`;
}

const MIN_SAMPLE = 20;

function speedEvaluation(
    p95: number | null,
    requests: number,
    p50?: number | null
): { label: string; badge: string } {
    if (requests < MIN_SAMPLE) {
        return {
            label: "Low Sample",
            badge: "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400",
        };
    }
    // Fast: median response is under 250ms
    if (p50 !== null && p50 !== undefined && p50 <= 250 && (p95 === null || p95 <= 1600)) {
        return {
            label: "Fast",
            badge: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300",
        };
    }
    // Normal: median response is under 500ms
    if (p50 !== null && p50 !== undefined && p50 <= 500 && (p95 === null || p95 <= 3200)) {
        return {
            label: "Normal",
            badge: "bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300",
        };
    }
    // Moderate: median response is under 800ms
    if (p50 !== null && p50 !== undefined && p50 <= 800) {
        return {
            label: "Moderate",
            badge: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300",
        };
    }
    // High Latency: median exceeds 800ms
    return {
        label: "High Latency",
        badge: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300",
    };
}

function ServiceCard({
    icon: Icon,
    title,
    status,
    detail,
    subDetail,
    help,
}: {
    icon: typeof Database;
    title: string;
    status: ServiceStatus;
    detail: string;
    subDetail?: string;
    help?: string;
}) {
    const cfg = STATUS_CONFIG[status];
    return (
        <div
            className={`rounded-2xl border p-5 flex flex-col justify-between shadow-sm transition hover:shadow-md ${cfg.border} bg-white dark:bg-slate-900`}
        >
            <div>
                <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 text-slate-700 dark:text-slate-300">
                            <Icon className="h-4 w-4" />
                        </div>
                        <span className="font-semibold text-sm text-slate-900 dark:text-white">{title}</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                        <span className="relative flex h-2 w-2">
                            {status === "ok" && (
                                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${cfg.dot}`} />
                            )}
                            <span className={`relative inline-flex rounded-full h-2 w-2 ${cfg.dot}`} />
                        </span>
                        <Badge variant="outline" className={`text-[10px] font-medium ${cfg.badge}`}>
                            {cfg.label}
                        </Badge>
                    </div>
                </div>

                <p className="text-base font-bold text-slate-900 dark:text-white">{detail}</p>
                {subDetail && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{subDetail}</p>}
            </div>

            {help && status !== "ok" && (
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs text-rose-600 dark:text-rose-400 font-medium">
                    {help}
                </div>
            )}
        </div>
    );
}

function Tile({
    label,
    value,
    hint,
    icon: Icon,
    trendGood,
}: {
    label: string;
    value: string;
    hint: string;
    icon: typeof Activity;
    trendGood?: boolean;
}) {
    return (
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    {label}
                </span>
                <Icon className="h-4 w-4 text-slate-400" />
            </div>
            <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">{value}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 flex items-center gap-1">
                {hint}
            </div>
        </div>
    );
}

function overall(data: SystemHealth): ServiceStatus {
    const statuses = Object.values(data.services).map((s) => s.status);
    if (statuses.includes("down")) return "down";
    if (statuses.includes("warning")) return "warning";
    return "ok";
}

const BANNER: Record<
    ServiceStatus,
    { title: string; text: string; icon: typeof CheckCircle2; tone: "good" | "warn" | "bad" }
> = {
    ok: {
        title: "All Infrastructure Subsystems Operational",
        text: "Database connections, memory cache, message queues, and async background workers are responding within normal parameters.",
        icon: CheckCircle2,
        tone: "good",
    },
    warning: {
        title: "Subsystem Degradation Detected",
        text: "Some asynchronous queues or database queries are experiencing elevated latency. Review the service breakdown below.",
        icon: AlertTriangle,
        tone: "warn",
    },
    down: {
        title: "Critical Service Interruption",
        text: "One or more foundational services (PostgreSQL, Redis, or Celery) are failing health checks. Immediate sysadmin action required.",
        icon: XCircle,
        tone: "bad",
    },
};

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
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                        System Health & Telemetry
                    </h1>
                    <Badge variant="outline" className="border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/50 text-xs">
                        DevOps Pulse
                    </Badge>
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Real-time operational status, database query latency, background queue throughput, and HTTP endpoint telemetry.
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
                {isFetching ? "Polling Telemetry..." : "Refresh Status"}
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
                <p className="text-xs text-slate-500 text-center">
                    If this health probe continues to fail, the backend Django process or reverse proxy may be unreachable.
                </p>
            </div>
        );
    }

    const state = overall(data);
    const bannerInfo = BANNER[state];
    const BannerIcon = bannerInfo.icon;
    const { database, cache, background_jobs: jobs, email_queue: email } = data.services;
    const api = data.api;
    const errorRate = api && api.requests ? (api.server_errors / api.requests) * 100 : 0;

    return (
        <div className="space-y-6 max-w-6xl">
            {header}

            {/* Master Health Status Banner */}
            <div
                className={`flex items-start gap-3.5 p-4 rounded-2xl border ${
                    bannerInfo.tone === "good"
                        ? "bg-emerald-50/80 text-emerald-900 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-200 dark:border-emerald-900"
                        : bannerInfo.tone === "warn"
                        ? "bg-amber-50/80 text-amber-900 border-amber-200 dark:bg-amber-950/30 dark:text-amber-200 dark:border-amber-900"
                        : "bg-rose-50/80 text-rose-900 border-rose-200 dark:bg-rose-950/30 dark:text-rose-200 dark:border-rose-900"
                }`}
            >
                <BannerIcon className="h-5 w-5 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-xs font-bold uppercase tracking-wider">{bannerInfo.title}</h4>
                        <span className="text-[11px] opacity-75 shrink-0 flex items-center gap-1 font-mono">
                            <Clock className="h-3 w-3" /> Checked {ago(data.checked_at, now)}
                        </span>
                    </div>
                    <p className="text-xs mt-0.5 leading-relaxed opacity-90">{bannerInfo.text}</p>
                </div>
            </div>

            {/* Core Infrastructure Services Strip */}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <ServiceCard
                    icon={Database}
                    title="PostgreSQL Master"
                    status={database.status}
                    detail={database.status === "ok" ? `${formatMs(database.ms)} ping` : "Unresponsive"}
                    subDetail="Direct connection pool check"
                    help="Active database query failed. Check PostgreSQL container."
                />
                <ServiceCard
                    icon={HardDrive}
                    title="Redis Memory Cache"
                    status={cache.status}
                    detail={cache.status === "ok" ? `${formatMs(cache.ms)} ping` : "Unresponsive"}
                    subDetail="Session store & fast cache layer"
                    help="Cache ping failed. Background workers and cached queries will degrade."
                />
                <ServiceCard
                    icon={Workflow}
                    title="Celery Async Workers"
                    status={jobs.status}
                    detail={jobs.status === "ok" ? `Active (last: ${ago(jobs.last_seen, now)})` : jobs.last_seen ? `Heartbeat lost (${ago(jobs.last_seen, now)})` : "Not running"}
                    subDetail="Scheduled tasks & fee reminders"
                    help="Background worker heartbeat not received. Restart Celery worker & beat."
                />
                <ServiceCard
                    icon={Mail}
                    title="Outbound Mail Queue"
                    status={email.status}
                    detail={email.waiting === undefined ? "Queue unavailable" : `${email.waiting} queued · ${email.sent_24h ?? 0} sent`}
                    subDetail={email.failed_24h ? `${email.failed_24h} failed in 24h` : "Zero bounce rate in 24h"}
                    help="Elevated failure count in outbound SMTP relay. Check email provider credentials."
                />
            </div>

            {/* API Speed & Traffic Telemetry Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200/80 dark:border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                        <Zap className="h-5 w-5 text-sky-600" />
                        <h2 className="text-base font-bold text-slate-900 dark:text-white">
                            API Performance & Response Times (Last 24 Hours)
                        </h2>
                    </div>
                    <p className="text-xs text-slate-500">
                        Aggregated endpoint latency for this institutional tenant
                    </p>
                </div>

                {!api ? (
                    <EmptyState
                        title="Latency metrics currently unavailable"
                        description="The fast Redis cache store is unreachable. Telemetry figures will resume once cache connectivity is restored."
                        className="py-12 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800"
                    />
                ) : api.requests === 0 ? (
                    <EmptyState
                        title="Zero API requests recorded in the last 24 hours"
                        description="Activity telemetry will appear here as users access dashboard portals and execute workflows."
                        className="py-12 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800"
                    />
                ) : (
                    <>
                        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                            <Tile
                                icon={Activity}
                                label="Total Invocations"
                                value={api.requests.toLocaleString("en-IN")}
                                hint="API requests served in last 24h"
                            />
                            <Tile
                                icon={Timer}
                                label="Typical Latency (p50)"
                                value={formatMs(api.p50_ms)}
                                hint="50% of requests completed faster"
                            />
                            <Tile
                                icon={Clock}
                                label="Worst 5% Latency (p95)"
                                value={api.requests < MIN_SAMPLE ? "—" : formatMs(api.p95_ms)}
                                hint={
                                    api.requests < MIN_SAMPLE
                                        ? `Requires ${MIN_SAMPLE} samples minimum`
                                        : "Under 800ms considered high-performance"
                                }
                            />
                            <Tile
                                icon={AlertTriangle}
                                label="5xx Server Errors"
                                value={`${api.server_errors}`}
                                hint={`${errorRate.toFixed(2)}% failure rate`}
                            />
                        </div>

                        {/* Endpoints Latency Matrix */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <Server className="h-4 w-4 text-slate-500" />
                                    <span>Endpoint Latency Breakdown</span>
                                </h3>
                                <p className="text-xs text-slate-500 flex items-center gap-1">
                                    <Timer className="h-3 w-3" /> Ranked by request volume and latency
                                </p>
                            </div>

                            <TableShell>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="font-semibold text-xs">Method & Endpoint</TableHead>
                                            <TableHead className="w-28 text-right font-semibold text-xs">Requests</TableHead>
                                            <TableHead className="w-28 text-right font-semibold text-xs">Typical (p50)</TableHead>
                                            <TableHead className="w-28 text-right font-semibold text-xs">Slowest 5% (p95)</TableHead>
                                            <TableHead className="w-24 text-right font-semibold text-xs">Server Errors</TableHead>
                                            <TableHead className="w-28 text-center font-semibold text-xs">Rating</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {[...api.endpoints]
                                            .sort((x, y) => Number(y.requests >= MIN_SAMPLE) - Number(x.requests >= MIN_SAMPLE))
                                            .map((r) => {
                                                const ev = speedEvaluation(r.p95_ms, r.requests, r.p50_ms);
                                                const methodBadge = METHOD_BADGES[r.method] ?? "bg-slate-100 text-slate-700";
                                                return (
                                                    <TableRow key={`${r.method} ${r.endpoint}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                                        <TableCell>
                                                            <div className="flex items-center gap-2 font-mono text-xs">
                                                                <Badge variant="outline" className={`text-[10px] px-1.5 py-0 font-bold ${methodBadge}`}>
                                                                    {r.method}
                                                                </Badge>
                                                                <span className="text-slate-800 dark:text-slate-200 font-medium truncate max-w-md">
                                                                    {r.endpoint}
                                                                </span>
                                                            </div>
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                                            {r.requests.toLocaleString("en-IN")}
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                                            {formatMs(r.p50_ms)}
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                                                            {r.requests < MIN_SAMPLE ? (
                                                                <span className="text-slate-400" title={`Needs at least ${MIN_SAMPLE} requests`}>
                                                                    —
                                                                </span>
                                                            ) : (
                                                                formatMs(r.p95_ms)
                                                            )}
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-xs">
                                                            {r.server_errors > 0 ? (
                                                                <span className="text-rose-600 dark:text-rose-400 font-bold">
                                                                    {r.server_errors}
                                                                </span>
                                                            ) : (
                                                                <span className="text-slate-400">0</span>
                                                            )}
                                                        </TableCell>
                                                        <TableCell className="text-center">
                                                            <Badge variant="outline" className={`text-[10px] font-medium ${ev.badge}`}>
                                                                {ev.label}
                                                            </Badge>
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
