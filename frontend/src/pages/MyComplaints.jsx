import React, { useState, useEffect } from 'react';
import { complaintAPI } from '../services/api';
import { FileText, Clock, CheckCircle2, AlertTriangle, Loader2, MapPin, ExternalLink } from 'lucide-react';
import { formatSlaStatus, getSlaClass } from '../utils/sla';
import { imageVerificationClass, imageVerificationLabel } from '../utils/imageVerification';

function mapsUrl(lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

const STATUS_CONFIG = {
  pending: { color: 'bg-yellow-100 text-yellow-700', icon: Clock, label: 'Pending' },
  assigned: { color: 'bg-blue-100 text-blue-700', icon: FileText, label: 'Assigned' },
  in_progress: { color: 'bg-indigo-100 text-indigo-700', icon: Loader2, label: 'In Progress' },
  resolved: { color: 'bg-green-100 text-green-700', icon: CheckCircle2, label: 'Resolved' },
  escalated: { color: 'bg-red-100 text-red-700', icon: AlertTriangle, label: 'Escalated' },
};

export default function MyComplaints() {
  const [complaints, setComplaints] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadComplaints();
  }, []);

  const loadComplaints = async () => {
    try {
      const { data } = await complaintAPI.getMine();
      setComplaints(data.complaints);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load complaints:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">My Complaints</h1>
          <p className="text-slate-500">{total} total complaint(s)</p>
        </div>
      </div>

      {complaints.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">No complaints yet.</p>
          <a href="/submit" className="text-brand-600 text-sm font-medium hover:underline">
            Report your first issue →
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {complaints.map((c) => {
            const statusConf = STATUS_CONFIG[c.status] || STATUS_CONFIG.pending;
            const StatusIcon = statusConf.icon;

            return (
              <div key={c.ticket_id} className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-sm transition">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-xs font-mono text-slate-400">{c.ticket_id}</p>
                    <h3 className="font-semibold text-slate-700 mt-1">{c.description}</h3>
                  </div>
                  <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${statusConf.color}`}>
                    <StatusIcon className="w-3 h-3" />
                    {statusConf.label}
                  </span>
                </div>
                <div className="flex gap-6 text-sm text-slate-500 flex-wrap">
                  <span>Dept: <strong className="text-slate-700">{c.department_name}</strong></span>
                  <span>Category: <strong className="text-slate-700 capitalize">{c.category?.replace(/_/g, ' ')}</strong></span>
                  <span>Priority: <strong className="text-slate-700">{c.priority}/5</strong></span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSlaClass(c)}`}>
                    {formatSlaStatus(c)}
                  </span>
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
                  ) : c.location_text ? (
                    <span><MapPin className="w-3 h-3 inline" /> {c.location_text}</span>
                  ) : null}
                </div>
                {c.image_url && (
                  <div className="mt-3">
                    <img src={c.image_url} alt="Complaint" className="h-28 rounded-lg object-cover border border-slate-100" />
                    <span className={`inline-flex mt-2 px-2 py-1 rounded text-xs font-medium ${imageVerificationClass(c)}`}>
                      {imageVerificationLabel(c)}
                    </span>
                  </div>
                )}
                <p className="text-xs text-slate-400 mt-2">
                  Filed: {new Date(c.created_at).toLocaleString()}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
