import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import { PlusCircle, FileText, Search, MapPin, Zap, Globe } from 'lucide-react';

export default function CitizenHome() {
  const { user } = useAuth();

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-slate-800 mb-3">
          Welcome, {user?.full_name?.split(' ')[0]}
        </h1>
        <p className="text-lg text-slate-500 max-w-xl mx-auto">
          Report civic issues in your language. We'll route it to the right department automatically.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-12">
        <Link
          to="/submit"
          className="flex items-center gap-4 p-6 bg-brand-600 text-white rounded-2xl hover:bg-brand-700 transition group"
        >
          <div className="bg-white/20 p-3 rounded-xl group-hover:bg-white/30 transition">
            <PlusCircle className="w-7 h-7" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Report an Issue</h3>
            <p className="text-brand-100 text-sm">Describe your problem in any language</p>
          </div>
        </Link>

        <Link
          to="/my-complaints"
          className="flex items-center gap-4 p-6 bg-white border border-slate-200 rounded-2xl hover:border-brand-300 hover:shadow-sm transition group"
        >
          <div className="bg-slate-100 p-3 rounded-xl group-hover:bg-brand-50 transition">
            <FileText className="w-7 h-7 text-slate-600 group-hover:text-brand-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-700">My Complaints</h3>
            <p className="text-slate-400 text-sm">Track status of your reported issues</p>
          </div>
        </Link>
      </div>

      {/* Track by ID */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 mb-12">
        <div className="flex items-center gap-2 mb-4">
          <Search className="w-5 h-5 text-slate-500" />
          <h3 className="font-semibold text-slate-700">Track a Complaint</h3>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const id = e.target.ticketId.value.trim();
            if (id) window.location.href = `/track/${id}`;
          }}
          className="flex gap-3"
        >
          <input
            name="ticketId"
            placeholder="Enter Ticket ID (e.g., CB-2026-00001)"
            className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition text-sm"
          />
          <button
            type="submit"
            className="px-6 py-2.5 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-900 transition text-sm"
          >
            Track
          </button>
        </form>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { icon: Globe, title: 'Multilingual', desc: 'Report in Kannada, Hindi, or English' },
          { icon: Zap, title: 'AI-Powered', desc: 'Automatic routing to the right department' },
          { icon: MapPin, title: 'Location Aware', desc: 'Ward-level tracking and heatmaps' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="bg-white border border-slate-200 rounded-xl p-5 text-center">
            <Icon className="w-8 h-8 text-brand-500 mx-auto mb-3" />
            <h4 className="font-semibold text-slate-700 mb-1">{title}</h4>
            <p className="text-sm text-slate-400">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
