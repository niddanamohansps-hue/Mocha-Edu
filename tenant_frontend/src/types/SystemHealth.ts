export type ServiceStatus = "ok" | "warning" | "down";

export interface TimedService {
    status: ServiceStatus;
    ms: number | null;
}

export interface BackgroundJobs {
    status: ServiceStatus;
    last_seen: string | null;
}

export interface EmailQueue {
    status: ServiceStatus;
    waiting?: number;
    failed_24h?: number;
    sent_24h?: number;
}

export interface EndpointTiming {
    endpoint: string;
    method: string;
    requests: number;
    avg_ms: number;
    /**
     * Upper limit (ms) of the timing range that holds the median / 95th-percentile request, not an exact time:
     * times are counted in ranges of up to 25, 50, 100, 200, 400, 800, 1600 and 3200 ms. null means slower than
     * 3.2 seconds.
     */
    p50_ms: number | null;
    p95_ms: number | null;
    server_errors: number;
    client_errors: number;
}

export interface ApiTimings {
    hours: number;
    requests: number;
    avg_ms: number;
    p50_ms: number | null;
    p95_ms: number | null;
    server_errors: number;
    client_errors: number;
    endpoints: EndpointTiming[];
}

export interface SystemHealth {
    checked_at: string;
    /** True for platform operators, who also see the shared infrastructure (database, cache, background workers). */
    platform: boolean;
    services: {
        /** Platform operators only. */
        database?: TimedService;
        /** Platform operators only. */
        cache?: TimedService;
        /** Platform operators only. */
        background_jobs?: BackgroundJobs;
        /** This school's own email queue. */
        email_queue: EmailQueue;
    };
    api: ApiTimings | null;
}
