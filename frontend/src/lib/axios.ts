import axios from 'axios';

/** The backend's API root. NEXT_PUBLIC_API_URL may be given with or without the trailing /api. */
function apiBaseUrl(): string {
    const configured = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
    return configured.endsWith('/api') ? configured : `${configured}/api`;
}

const axiosInstance = axios.create({
    baseURL: apiBaseUrl(),
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

        if (
            originalRequest.url.includes('/auth/refresh/') ||
            originalRequest.url.includes('/auth/login/') ||
            originalRequest.url.includes('/auth/register/')
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
                return Promise.reject(err);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

export default axiosInstance;
