"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Database, HardDrive, Mail, RefreshCw, Timer, Workflow, XCircle, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { EmptyState } from "@/components/feedback/EmptyState";
import Unauthorized from "@/components/Unauthorized";
import { useSystemHealth } from "@/hooks/useSystemHealth";
import { usePermissions } from "@/providers/PermissionProvider";
import { ServiceStatus, SystemHealth } from "@/types/SystemHealth";

const STATUS_STYLE: Record<ServiceStatus, string> = {
    ok: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    warning: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    down: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
};
const STATUS_LABEL: Record<ServiceStatus, string> = { ok: "Working", warning: "Needs attention", down: "Not working" };

/** 1600 -> "1.6 s", 40 -> "40 ms", null -> "over 3.2 s" (slower than the slowest bucket). */
function formatMs(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "over 3.2 s";
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

function ago(iso: string | null, now: number): string {
    if (!iso) return "never";
    const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
    if (seconds < 60) return `${seconds} s ago`;
    if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
    return `${Math.round(seconds / 3600)} h ago`;
}

/** Below this many requests one slow call (e.g. the first after a restart) would decide "slowest 5%". */
const MIN_SAMPLE = 20;

function speed(p95: number | null, requests: number): { label: string; style: string } {
    if (requests < MIN_SAMPLE) return { label: "Too few", style: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" };
    if (p95 !== null && p95 <= 200) return { label: "Fast", style: STATUS_STYLE.ok };
    if (p95 !== null && p95 <= 800) return { label: "OK", style: STATUS_STYLE.warning };
    return { label: "Slow", style: STATUS_STYLE.down };
}

function StatusPill({ status }: { status: ServiceStatus }) {
    return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>;
}

function ServiceCard({ icon: Icon, title, status, detail, help }: {
    icon: typeof Database; title: string; status: ServiceStatus; detail: string; help?: string;
}) {
    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-2">
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium text-slate-900 dark:text-white">
                    <Icon className="h-4 w-4 text-slate-500" /> {title}
                </div>
                <StatusPill status={status} />
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300">{detail}</p>
            {help && status !== "ok" && <p className="text-xs text-slate-500 dark:text-slate-400">{help}</p>}
        </div>
    );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900 dark:text-white">{value}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{hint}</div>
        </div>
    );
}

function overall(data: SystemHealth): ServiceStatus {
    const statuses = Object.values(data.services).map((s) => s.status);
    if (statuses.includes("down")) return "down";
    if (statuses.includes("warning")) return "warning";
    return "ok";
}

const BANNER: Record<ServiceStatus, { text: string; icon: typeof CheckCircle2 }> = {
    ok: { text: "Everything is working.", icon: CheckCircle2 },
    warning: { text: "Everything is running, but something needs a look.", icon: AlertTriangle },
    down: { text: "Something is not working. See the red cards below.", icon: XCircle },
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
        <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">System Health</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Whether the server is working and how fast pages load. Updates every 30 seconds.
                </p>
            </div>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} /> Check now
            </Button>
        </div>
    );

    if (isLoading) return <div className="space-y-6">{header}<LoadingState className="py-16" /></div>;
    if (isError || !data) {
        return (
            <div className="space-y-6">
                {header}
                <ErrorState onRetry={refetch} />
                <p className="text-sm text-slate-500">If this keeps failing, the server itself may be down.</p>
            </div>
        );
    }

    const state = overall(data);
    const Banner = BANNER[state].icon;
    const { database, cache, background_jobs: jobs, email_queue: email } = data.services;
    const api = data.api;
    const errorRate = api && api.requests ? (api.server_errors / api.requests) * 100 : 0;

    return (
        <div className="space-y-6">
            {header}

            <div className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${STATUS_STYLE[state]}`}>
                <Banner className="h-5 w-5 shrink-0" />
                <div className="text-sm font-medium">{BANNER[state].text}</div>
                <div className="ml-auto text-xs opacity-80">Checked {ago(data.checked_at, now)}</div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <ServiceCard
                    icon={Database} title="Database" status={database.status}
                    detail={database.status === "ok" ? `Answering in ${formatMs(database.ms)}` : "Not answering"}
                    help="No page can load data. Check that PostgreSQL is running."
                />
                <ServiceCard
                    icon={HardDrive} title="Cache" status={cache.status}
                    detail={cache.status === "ok" ? `Answering in ${formatMs(cache.ms)}` : "Not answering"}
                    help="Pages still work but are slower, and background jobs stop. Check that Redis is running."
                />
                <ServiceCard
                    icon={Workflow} title="Background jobs" status={jobs.status}
                    detail={jobs.status === "ok" ? `Last ran ${ago(jobs.last_seen, now)}` : jobs.last_seen ? `Stopped. Last ran ${ago(jobs.last_seen, now)}` : "Not running"}
                    help="Alerts, fee reminders and emails are not being sent. Start the Celery worker and beat."
                />
                <ServiceCard
                    icon={Mail} title="Email queue" status={email.status}
                    detail={email.waiting === undefined ? "Could not read the queue" : `${email.waiting} waiting · ${email.failed_24h} failed · ${email.sent_24h} sent today`}
                    help="Some emails failed or many are waiting. Check the email settings and the background jobs."
                />
            </div>

            <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                    <Activity className="h-5 w-5 text-slate-500" /> Page speed, last 24 hours
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">How long the server took to answer this school&apos;s requests.</p>
            </div>

            {!api ? (
                <EmptyState title="Speed figures are not available right now (the cache is not answering)." className="py-10 text-slate-500 text-sm" />
            ) : api.requests === 0 ? (
                <EmptyState title="No requests yet in the last 24 hours." className="py-10 text-slate-500 text-sm" />
            ) : (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        <Tile label="Requests" value={api.requests.toLocaleString("en-IN")} hint="Pages and actions answered" />
                        <Tile label="Typical answer" value={formatMs(api.p50_ms)} hint="Half of requests were faster than this" />
                        <Tile
                            label="Slowest 5%"
                            value={api.requests < MIN_SAMPLE ? "—" : formatMs(api.p95_ms)}
                            hint={api.requests < MIN_SAMPLE ? `Shown after ${MIN_SAMPLE} requests` : "Under 800 ms feels quick to people"}
                        />
                        <Tile label="Server errors" value={`${api.server_errors}`} hint={`${errorRate.toFixed(2)}% of requests failed on the server`} />
                    </div>

                    <ResponsiveList
                        rows={[...api.endpoints].sort((x, y) => Number(y.requests >= MIN_SAMPLE) - Number(x.requests >= MIN_SAMPLE))}
                        rowKey={(r) => `${r.method} ${r.endpoint}`}
                        columns={[
                            {
                                key: "endpoint", header: "Request", primary: true, cell: (r) => (
                                    <span className="font-mono text-xs break-all">
                                        <span className="mr-2 rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5">{r.method}</span>{r.endpoint}
                                    </span>
                                ),
                            },
                            { key: "requests", header: "Requests", cell: (r) => r.requests.toLocaleString("en-IN") },
                            { key: "typical", header: "Typical", hideOnMobile: true, cell: (r) => formatMs(r.p50_ms) },
                            {
                                key: "p95", header: "Slowest 5%", cell: (r) => r.requests < MIN_SAMPLE
                                    ? <span className="text-slate-400" title={`Shown after ${MIN_SAMPLE} requests`}>—</span>
                                    : formatMs(r.p95_ms),
                            },
                            {
                                key: "errors", header: "Errors", cell: (r) => r.server_errors
                                    ? <span className="text-red-600 dark:text-red-400 font-medium">{r.server_errors}</span>
                                    : <span className="text-slate-400">0</span>,
                            },
                            {
                                key: "speed", header: "Speed", cell: (r) => {
                                    const s = speed(r.p95_ms, r.requests);
                                    return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.style}`}>{s.label}</span>;
                                },
                            },
                        ]}
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                        <Timer className="h-3.5 w-3.5" /> Slowest first. &ldquo;Too few&rdquo; means under {MIN_SAMPLE} requests: the first requests after a server restart are always slow. Times are server time only; the user&apos;s internet adds to it.
                    </p>
                </>
            )}
        </div>
    );
}
