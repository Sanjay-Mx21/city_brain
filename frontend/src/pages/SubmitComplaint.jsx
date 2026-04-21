import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { complaintAPI } from '../services/api';
import { Send, MapPin, Globe, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';

const PRIORITY_COLORS = {
  1: 'bg-green-100 text-green-700',
  2: 'bg-blue-100 text-blue-700',
  3: 'bg-yellow-100 text-yellow-700',
  4: 'bg-orange-100 text-orange-700',
  5: 'bg-red-100 text-red-700',
};

const PRIORITY_LABELS = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Urgent', 5: 'Critical' };

export default function SubmitComplaint() {
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const payload = { text: text.trim() };
      if (language) payload.language = language;

      // Try to get user location
      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          payload.latitude = pos.coords.latitude;
          payload.longitude = pos.coords.longitude;
        } catch {
          // Location not available, that's fine
        }
      }

      const { data } = await complaintAPI.submit(payload);
      setResult(data);
      toast.success(`${data.total_complaints_detected} complaint(s) registered!`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit complaint');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-slate-800 mb-2">Report a Civic Issue</h1>
      <p className="text-slate-500 mb-8">
        Describe your problem in any language. Our AI will understand it, classify it,
        and route it to the right department.
      </p>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Language selector */}
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              <Globe className="w-4 h-4 inline mr-1" />
              Language (optional — we auto-detect)
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition text-sm"
            >
              <option value="">Auto-detect</option>
              <option value="en">English</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
              <option value="hi">हिन्दी (Hindi)</option>
            </select>
          </div>

          {/* Complaint text */}
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              Describe your complaint
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              placeholder="e.g., Our road has been broken for 3 months and the streetlight near the park is not working. Also garbage is piling up near the bus stop."
              className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition text-sm resize-none"
              required
              minLength={5}
            />
            <p className="text-xs text-slate-400 mt-1">
              Tip: You can mention multiple issues in one message. We'll create separate tickets for each.
            </p>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-medium transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                AI is analyzing your complaint...
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                Submit Complaint
              </>
            )}
          </button>
        </form>
      ) : (
        /* Results */
        <div className="space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-3">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
              <h2 className="text-lg font-semibold text-green-800">{result.message}</h2>
            </div>
            <p className="text-sm text-green-600">
              We detected {result.total_complaints_detected} complaint(s) in your message.
            </p>
          </div>

          {/* Individual tickets */}
          {result.tickets?.map((ticket) => (
            <div key={ticket.ticket_id} className="bg-white border border-slate-200 rounded-xl p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-xs font-mono text-slate-400">{ticket.ticket_id}</p>
                  <h3 className="text-lg font-semibold text-slate-700 mt-1">{ticket.description}</h3>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${PRIORITY_COLORS[ticket.priority]}`}>
                  {PRIORITY_LABELS[ticket.priority]}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Department</p>
                  <p className="font-medium text-slate-700">{ticket.department_name}</p>
                </div>
                <div>
                  <p className="text-slate-400">Category</p>
                  <p className="font-medium text-slate-700 capitalize">
                    {ticket.category?.replace(/_/g, ' ')}
                  </p>
                </div>
                {ticket.location_text && (
                  <div>
                    <p className="text-slate-400">Location</p>
                    <p className="font-medium text-slate-700 flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {ticket.location_text}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-slate-400">AI Confidence</p>
                  <p className="font-medium text-slate-700">
                    {Math.round((ticket.ai_confidence || 0) * 100)}%
                  </p>
                </div>
              </div>
            </div>
          ))}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => { setResult(null); setText(''); }}
              className="flex-1 py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition"
            >
              Report Another Issue
            </button>
            <button
              onClick={() => navigate('/my-complaints')}
              className="flex-1 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition"
            >
              View All Complaints
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
