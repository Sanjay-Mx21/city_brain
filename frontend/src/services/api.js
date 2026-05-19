/**
 * City Brain — API Service
 * Centralized axios client for all backend API calls.
 */

import axios from 'axios';

const API_BASE = '/api/v1';

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
  transcribe: (audioBlob, language = '') => {
    const fd = new FormData();
    fd.append('file', audioBlob, 'recording.webm');
    return api.post(`/complaints/transcribe?language=${language}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ─── OFFICER ───
export const officerAPI = {
  getQueue: (status, page = 1) =>
    api.get(`/officer/queue?page=${page}${status ? `&status_filter=${status}` : ''}`),
  updateStatus: (complaintId, data) =>
    api.patch(`/officer/complaints/${complaintId}/status`, data),
  getStats: () => api.get('/officer/stats'),
};

// ─── ADMIN ───
export const adminAPI = {
  getDashboard: () => api.get('/admin/dashboard'),
  getHeatmap: () => api.get('/admin/heatmap'),
  getDepartments: () => api.get('/admin/departments'),
  getWards: () => api.get('/admin/wards'),
};

export default api;
