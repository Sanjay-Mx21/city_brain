import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { complaintAPI } from '../services/api';
import { Brain, Search, Loader2, CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

export default function TrackComplaint() {
  const { ticketId } = useParams();
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchId, setSearchId] = useState(ticketId || '');

  useEffect(() => {
    if (ticketId) fetchComplaint(ticketId);
  }, [ticketId]);

  const fetchComplaint = async (id) => {
    setLoading(true);
    setError('');
    try {
      const { data } = await complaintAPI.track(id);
      setComplaint(data);
    } catch {
      setError('Ticket not found. Please check the ID and try again.');
      setComplaint(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="text-center mb-8">
        <Brain className="w-10 h-10 text-brand-600 mx-auto mb-3" />
        <h1 className="text-2xl font-bold text-slate-800">Track Your Complaint</h1>
        <p className="text-slate-500">Enter your ticket ID to see the current status</p>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); if (searchId.trim()) fetchComplaint(searchId.trim()); }}
        className="flex gap-3 mb-8"
      >
        <input
          value={searchId}
          onChange={(e) => setSearchId(e.target.value)}
          placeholder="CB-2026-00001"
          className="flex-1 px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 outline-none text-sm"
        />
        <button type="submit" disabled={loading}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition disabled:opacity-50">
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
        </button>
      </form>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">{error}</div>
      )}

      {complaint && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-mono text-slate-400">{complaint.ticket_id}</p>
              <h2 className="text-xl font-bold text-slate-800 mt-1">{complaint.description}</h2>
            </div>
            <StatusBadge status={complaint.status} />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <Detail label="Department" value={complaint.department_name} />
            <Detail label="Category" value={complaint.category?.replace(/_/g, ' ')} />
            <Detail label="Priority" value={`${complaint.priority}/5`} />
            <Detail label="Location" value={complaint.location_text || 'N/A'} />
            <Detail label="Filed On" value={new Date(complaint.created_at).toLocaleString()} />
            <Detail label="Last Updated" value={new Date(complaint.updated_at).toLocaleString()} />
            {complaint.resolved_at && (
              <Detail label="Resolved On" value={new Date(complaint.resolved_at).toLocaleString()} />
            )}
          </div>

          {complaint.translated_text && complaint.original_language !== 'en' && (
            <div className="bg-slate-50 rounded-lg p-4">
              <p className="text-xs text-slate-400 mb-1">Original ({complaint.original_language})</p>
              <p className="text-sm text-slate-600">{complaint.original_text}</p>
              <p className="text-xs text-slate-400 mt-2 mb-1">Translated</p>
              <p className="text-sm text-slate-600">{complaint.translated_text}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const config = {
    pending: { bg: 'bg-yellow-100 text-yellow-700', label: 'Pending' },
    assigned: { bg: 'bg-blue-100 text-blue-700', label: 'Assigned' },
    in_progress: { bg: 'bg-indigo-100 text-indigo-700', label: 'In Progress' },
    resolved: { bg: 'bg-green-100 text-green-700', label: 'Resolved' },
    escalated: { bg: 'bg-red-100 text-red-700', label: 'Escalated' },
  };
  const c = config[status] || config.pending;
  return <span className={`px-3 py-1 rounded-full text-xs font-medium ${c.bg}`}>{c.label}</span>;
}

function Detail({ label, value }) {
  return (
    <div>
      <p className="text-slate-400">{label}</p>
      <p className="font-medium text-slate-700 capitalize">{value}</p>
    </div>
  );
}
