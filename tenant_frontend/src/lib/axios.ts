import axios from 'axios';

const getBaseURL = () => {
    if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        // If we are on a subdomain like org.localhost
        if (hostname.includes('.localhost')) {
            const subdomain = hostname.split('.')[0];
            return `http://${subdomain}.localhost:8000/api`;
        }
    }
    return 'http://localhost:8000/api';
};

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
