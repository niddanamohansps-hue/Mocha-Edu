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
    /** null means slower than the slowest bucket (over 3.2 seconds). */
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
    services: {
        database: TimedService;
        cache: TimedService;
        background_jobs: BackgroundJobs;
        email_queue: EmailQueue;
    };
    api: ApiTimings | null;
}
