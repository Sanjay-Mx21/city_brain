import React, { useState, useEffect } from 'react';
import { adminAPI, officerAPI } from '../services/api';
import { Loader2, CheckCircle2, Clock, AlertTriangle, MapPin, ExternalLink } from 'lucide-react';
import toast from 'react-hot-toast';
import { formatSlaStatus, getSlaClass } from '../utils/sla';
import { imageVerificationClass, imageVerificationLabel } from '../utils/imageVerification';

function mapsUrl(lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

export default function OfficerDashboard() {
  const [complaints, setComplaints] = useState([]);
  const [stats, setStats] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [departmentFilter, setDepartmentFilter] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('priority');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDepartments();
  }, []);

  useEffect(() => { load(); }, [statusFilter, departmentFilter, sortBy]);

  const loadDepartments = async () => {
    try {
      const { data } = await adminAPI.getDepartments();
      setDepartments(data);
    } catch {
      toast.error('Failed to load organizations');
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const selectedDepartment = Number(departmentFilter);
      const [queueRes, statsRes] = await Promise.all([
        officerAPI.getQueue(statusFilter, 1, selectedDepartment, sortBy),
        officerAPI.getStats(selectedDepartment),
      ]);
      setComplaints(queueRes.data.complaints);
      setStats(statsRes.data);
    } catch (err) {
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (complaintId, newStatus) => {
    try {
      await officerAPI.updateStatus(complaintId, { status: newStatus });
      toast.success(`Complaint updated to ${newStatus}`);
      load(); // Refresh
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed');
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Officer Dashboard</h1>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-8">
          <StatCard label="Total" value={stats.total_assigned} color="slate" />
          <StatCard label="Pending" value={stats.pending} color="yellow" />
          <StatCard label="In Progress" value={stats.in_progress} color="blue" />
          <StatCard label="Resolved" value={stats.resolved} color="green" />
          <StatCard label="Escalated" value={stats.escalated} color="red" />
          <StatCard label="Overdue" value={stats.overdue} color="red" />
          <StatCard label="Due Soon" value={stats.due_soon} color="orange" />
        </div>
      )}

      {/* Filters */}
      <div className="mb-6 flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Organization
          </label>
          <select
            value={departmentFilter}
            onChange={(event) => setDepartmentFilter(Number(event.target.value))}
            className="min-w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          >
            <option value={0}>All organizations</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name} - {department.full_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setStatusFilter('');
              setSortBy('latest');
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              sortBy === 'latest'
                ? 'bg-brand-600 text-white'
                : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100'
            }`}
          >
            Latest Complaints
          </button>
          {['', 'pending', 'in_progress', 'resolved', 'escalated'].map((s) => (
            <button
              key={s}
              onClick={() => {
                setStatusFilter(s);
                setSortBy('priority');
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                sortBy === 'priority' && statusFilter === s
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100'
              }`}
            >
              {s === '' ? 'All' : s.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
            </button>
          ))}
        </div>
      </div>

      {/* Complaints Queue */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
        </div>
      ) : complaints.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
          <CheckCircle2 className="w-12 h-12 text-green-300 mx-auto mb-3" />
          <p className="text-slate-500">No complaints in this category. Great work!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {complaints.map((c) => (
            <div key={c.id} className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <p className="text-xs font-mono text-slate-400">{c.ticket_id}</p>
                    <PriorityBadge priority={c.priority} />
                    <StatusBadge status={c.status} />
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSlaClass(c)}`}>
                      {formatSlaStatus(c)}
                    </span>
                  </div>
                  <h3 className="font-semibold text-slate-700">{c.description}</h3>
                  <div className="flex items-center gap-3 text-sm text-slate-400 mt-1 flex-wrap">
                    <span>{c.department_name || 'Unassigned'}</span>
                    <span className="text-slate-300">|</span>
                    <span>{c.category?.replace(/_/g, ' ')}</span>
                    <span className="text-slate-300">|</span>
                    {c.latitude && c.longitude ? (
                      <a
                        href={mapsUrl(c.latitude, c.longitude)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-brand-600 hover:underline"
                      >
                        <MapPin className="w-3 h-3" />
                        {c.location_text || 'View on Maps'}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span>{c.location_text || 'No location'}</span>
                    )}
                    <span className="text-slate-300">|</span>
                    <span>Filed {new Date(c.created_at).toLocaleDateString()}</span>
                  </div>
                  {c.image_url && (
                    <div className="mt-2">
                      <img src={c.image_url} alt="Complaint" className="h-24 rounded-lg object-cover border border-slate-100" />
                      <span className={`inline-flex mt-2 px-2 py-1 rounded text-xs font-medium ${imageVerificationClass(c)}`}>
                        {imageVerificationLabel(c)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 ml-4">
                  {c.status === 'pending' && (
                    <ActionBtn onClick={() => updateStatus(c.id, 'in_progress')} color="blue" label="Start Work" />
                  )}
                  {(c.status === 'pending' || c.status === 'in_progress') && (
                    <ActionBtn onClick={() => updateStatus(c.id, 'resolved')} color="green" label="Resolve" />
                  )}
                  {c.status !== 'escalated' && c.status !== 'resolved' && (
                    <ActionBtn onClick={() => updateStatus(c.id, 'escalated')} color="red" label="Escalate" />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    slate: 'bg-slate-50 text-slate-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    red: 'bg-red-50 text-red-700',
    orange: 'bg-orange-50 text-orange-700',
  };
  return (
    <div className={`rounded-xl p-4 ${colors[color]}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm opacity-70">{label}</p>
    </div>
  );
}

function PriorityBadge({ priority }) {
  const colors = { 1: 'bg-green-100 text-green-600', 2: 'bg-blue-100 text-blue-600', 3: 'bg-yellow-100 text-yellow-600', 4: 'bg-orange-100 text-orange-600', 5: 'bg-red-100 text-red-600' };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[priority] || colors[2]}`}>P{priority}</span>;
}

function StatusBadge({ status }) {
  const config = { pending: 'bg-yellow-100 text-yellow-700', assigned: 'bg-blue-100 text-blue-700', in_progress: 'bg-indigo-100 text-indigo-700', resolved: 'bg-green-100 text-green-700', escalated: 'bg-red-100 text-red-700' };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${config[status] || config.pending}`}>{status?.replace(/_/g, ' ')}</span>;
}

function ActionBtn({ onClick, color, label }) {
  const colors = { blue: 'bg-blue-50 text-blue-600 hover:bg-blue-100', green: 'bg-green-50 text-green-600 hover:bg-green-100', red: 'bg-red-50 text-red-600 hover:bg-red-100' };
  return (
    <button onClick={onClick} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${colors[color]}`}>
      {label}
    </button>
  );
}
