import axios from 'axios';
import { toast } from 'sonner';
import { apiBaseUrl } from './apiBase';

let lastReadOnlyNotice = 0;

function showReadOnlyNotice(message: string) {
    if (Date.now() - lastReadOnlyNotice < 10_000) return;
    lastReadOnlyNotice = Date.now();
    toast.error(message || "This school is read-only until the subscription is paid.", {
        id: "subscription-read-only",
        duration: 10_000,
        action: { label: "Go to Billing", onClick: () => window.location.assign("/dashboard/billing") },
    });
}

const getBaseURL = apiBaseUrl;

const axiosInstance = axios.create({
    baseURL: getBaseURL(),
    withCredentials: true,
});

let isRefreshing = false;
let failedQueue: { resolve: (token?: any) => void; reject: (err: any) => void }[] = [];

const processQueue = (error: any, token: any = null) => {
    failedQueue.forEach(prom => {
        if (error) prom.reject(error);
        else prom.resolve(token);
    });
    failedQueue = [];
};

axiosInstance.interceptors.response.use(
    res => res,
    async error => {
        const originalRequest = error.config;

        if (!originalRequest || !error.response) return Promise.reject(error);

        // The school's subscription is unpaid: changes are refused, reading still works. One clear
        // message (not repeated for every failed call) with a way to the Billing page.
        if (error.response.status === 402 && error.response.data?.code === "subscription_read_only") {
            showReadOnlyNotice(error.response.data.error);
            return Promise.reject(error);
        }

        if (
            originalRequest.url.includes('/auth/refresh/') ||
            originalRequest.url.includes('/auth/login/') ||
            originalRequest.url.includes('/auth/register/') ||
            originalRequest.url.includes('/admissions/public/')
        ) {
            return Promise.reject(error);
        }

        if (error.response.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then(() => axiosInstance(originalRequest));
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                await axiosInstance.post('/auth/refresh/');
                processQueue(null);
                return axiosInstance(originalRequest);
            } catch (err) {
                processQueue(err, null);
                if (
                    typeof window !== 'undefined' &&
                    !window.location.pathname.startsWith('/login') &&
                    !window.location.pathname.startsWith('/apply') &&
                    !window.location.pathname.startsWith('/admissions/status')
                ) {
                    localStorage.removeItem("active_role");
                    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
                    window.location.href = '/login?session_expired=true';
                }
                return Promise.reject(err);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

export default axiosInstance;
