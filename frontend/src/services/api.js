/**
 * City Brain — API Service
 * Centralized axios client for all backend API calls.
 */

import axios from 'axios';

// Same-origin '/api/v1' by default (nginx or the Vite dev proxy forwards it).
// Set VITE_API_BASE_URL (e.g. https://api.example.com/api/v1) when the
// backend is hosted on a different domain.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const API_ORIGIN = API_BASE.startsWith('http') ? new URL(API_BASE).origin : '';

// Resolve backend-relative media paths such as '/uploads/abc.png'.
export const mediaUrl = (path) => (path && path.startsWith('/') ? `${API_ORIGIN}${path}` : path);

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cb_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 → redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cb_token');
      localStorage.removeItem('cb_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── AUTH ───
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getProfile: () => api.get('/auth/me'),
};

// ─── COMPLAINTS ───
export const complaintAPI = {
  submit: (data) => api.post('/complaints/submit', data),
  getMine: (page = 1) => api.get(`/complaints/my?page=${page}`),
  track: (ticketId) => api.get(`/complaints/track/${ticketId}`),
  uploadImage: (complaintId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.post(`/complaints/${complaintId}/image`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  transcribe: (audioBlob, language = '', translate = true) => {
    const fd = new FormData();
    fd.append('file', audioBlob, 'recording.webm');
    return api.post('/complaints/transcribe', fd, {
      params: { language, translate },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ASSISTANT
export const assistantAPI = {
  chat: (data) => api.post('/assistant/chat', data),
};

// OFFICER
export const officerAPI = {
  getQueue: (status, page = 1, departmentId = 0, sortBy = 'priority') =>
    api.get('/officer/queue', {
      params: {
        page,
        department_id: departmentId,
        sort_by: sortBy,
        ...(status ? { status_filter: status } : {}),
      },
    }),
  updateStatus: (complaintId, data) =>
    api.patch(`/officer/complaints/${complaintId}/status`, data),
  getStats: (departmentId = 0) => api.get('/officer/stats', {
    params: { department_id: departmentId },
  }),
};

// ─── ADMIN ───
export const adminAPI = {
  getDashboard: () => api.get('/admin/dashboard'),
  getHeatmap: () => api.get('/admin/heatmap'),
  getDepartments: () => api.get('/admin/departments'),
  getWards: () => api.get('/admin/wards'),
};

export default api;
