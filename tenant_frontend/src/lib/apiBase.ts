/**
 * Where the browser sends API calls.
 *
 * Production (NEXT_PUBLIC_API_SAME_ORIGIN=true): the same host the page came from, under /api. The proxy or
 * CDN in front routes /api to the backend, and the host name still tells the backend which school it is.
 * Development (default): school.localhost:3555 talks to school.localhost:8000.
 */
export function apiBaseUrl(): string {
    if (typeof window !== "undefined") {
        if (process.env.NEXT_PUBLIC_API_SAME_ORIGIN === "true") {
            return `${window.location.origin}/api`;
        }
        const hostname = window.location.hostname;
        if (hostname.includes(".localhost")) {
            return `http://${hostname.split(".")[0]}.localhost:8000/api`;
        }
    }
    return "http://localhost:8000/api";
}
