import axios from 'axios';

// Base URL cho API:
// - Dev: dùng VITE_API_BASE_URL (vd: http://VPS_IP:8000/api) hoặc fallback localhost (proxy bởi vite)
// - Production (FE serve từ BE): dùng '/api' relative → cùng host/port, không cần config
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// WebSocket URL:
// - Dev: dùng VITE_WS_BASE_URL hoặc ws://localhost:8000
// - Production: tự động dùng cùng host (ws → wss nếu https)
const _wsProto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
const _wsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || `${_wsProto}://${_wsHost}`;

// Tạo axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error?.response?.status === 401) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('current_user');
        }
        return Promise.reject(error);
    }
);

// ============== Auth API ==============

export const authAPI = {
    register: (data) => api.post('/auth/register', data),
    login: (data) => api.post('/auth/login', data),
    refresh: (data) => api.post('/auth/refresh', data),
    me: () => api.get('/auth/me'),
    changePassword: (data) => api.post('/auth/change-password', data),
    forgotPassword: (data) => api.post('/auth/forgot-password', data),
    resetPassword: (data) => api.post('/auth/reset-password', data),
};

// ============== Config API ==============

export const configAPI = {
    get: () => api.get('/config'),
    update: (data) => api.post('/config', data),
    getCredentials: () => api.get('/config/credentials'),
    reset: () => api.delete('/config'),
};

// ============== RPA API ==============

export const rpaAPI = {
    getStatus: () => api.get('/rpa/status'),

    // Session management
    checkSession: () => api.get('/rpa/session'),                              // Fast: trả cache, không mở browser
    verifySession: () => api.get('/rpa/session', { params: { force: true } }), // Slow: check thật qua Playwright
    login: (data) => api.post('/rpa/login', data),
    logout: () => api.post('/rpa/logout'),

    // RPA tasks
    checkContracts: (data) => api.post('/rpa/check-contracts', data),
    downloadFiles: (data) => api.post('/rpa/download-files', data),
    scrapeDetails: (data) => api.post('/rpa/scrape-details', data),

    // Control
    pause: () => api.post('/rpa/pause'),
    resume: () => api.post('/rpa/resume'),
    stop: () => api.post('/rpa/stop'),
};

// ============== Zalo API ==============

export const zaloAPI = {
    // Session
    getSession: () => api.get('/zalo/session'),
    verifySession: () => api.get('/zalo/session', { params: { verify: true } }),
    getQR: () => api.get('/zalo/qr'),
    login: () => api.post('/zalo/login'),
    logout: () => api.post('/zalo/logout'),

    // Automation
    sendMessages: (data) => api.post('/zalo/send-messages', data),
    addFriends: (data) => api.post('/zalo/add-friends', data),

    pause: () => api.post('/zalo/pause'),
    resume: () => api.post('/zalo/resume'),
    stop: () => api.post('/zalo/stop'),
};

// ============== Files API ==============

export const filesAPI = {
    upload: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return api.post('/files/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    },

    parseExcel: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return api.post('/files/parse-excel', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    },

    list: (directory = 'downloads') => api.get('/files/list', { params: { directory } }),
    listDownloads: () => api.get('/files/list', { params: { directory: 'downloads' } }),
    download: (filename, directory = 'downloads') =>
        `${API_BASE_URL}/files/download/${filename}?directory=${directory}`,
    delete: (filename, directory = 'uploads') =>
        api.delete(`/files/${filename}`, { params: { directory } }),
    templateUrl: () => `${API_BASE_URL}/files/template`,
};

// ============== SMS Gateway API ==============

export const smsAPI = {
    getConfig: () => api.get('/sms/config'),
    saveConfig: (data) => api.post('/sms/config', data),
    send: (data) => api.post('/sms/send', data),
    health: () => api.get('/sms/health'),
    getMessages: (limit = 100) => api.get('/sms/messages', { params: { limit } }),
    clearMessages: () => api.delete('/sms/messages'),
};

// ============== Health Check ==============

export const healthAPI = {
    check: () => api.get('/health'),
};

export { WS_BASE_URL };
export default api;
