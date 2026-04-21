import React, { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Loader2, TrendingUp, Clock, AlertTriangle, CheckCircle2, Building2 } from 'lucide-react';

const COLORS = ['#2563eb', '#059669', '#ea580c', '#dc2626', '#7c3aed', '#ca8a04'];

export default function AdminDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const { data } = await adminAPI.getDashboard();
      setDashboard(data);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
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

  if (!dashboard) {
    return <div className="text-center py-20 text-slate-500">Failed to load dashboard data.</div>;
  }

  const statusData = [
    { name: 'Pending', value: dashboard.pending, color: '#eab308' },
    { name: 'In Progress', value: dashboard.in_progress, color: '#3b82f6' },
    { name: 'Resolved', value: dashboard.resolved, color: '#22c55e' },
    { name: 'Escalated', value: dashboard.escalated, color: '#ef4444' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">City Admin Dashboard</h1>
          <p className="text-slate-500">Real-time civic intelligence overview for Bengaluru</p>
        </div>
        <button
          onClick={loadDashboard}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition"
        >
          Refresh Data
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <KPICard icon={Building2} label="Total Complaints" value={dashboard.total_complaints} color="slate" />
        <KPICard icon={Clock} label="Pending" value={dashboard.pending} color="yellow" />
        <KPICard icon={TrendingUp} label="In Progress" value={dashboard.in_progress} color="blue" />
        <KPICard icon={CheckCircle2} label="Resolved" value={dashboard.resolved} color="green" />
        <KPICard icon={AlertTriangle} label="Escalated" value={dashboard.escalated} color="red" />
        <KPICard icon={Clock} label="Avg Resolution" value={dashboard.avg_resolution_hours ? `${dashboard.avg_resolution_hours}h` : 'N/A'} color="purple" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Status Distribution Pie */}
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h3 className="font-semibold text-slate-700 mb-4">Complaint Status Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%" cy="50%"
                outerRadius={90}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {statusData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Department Stats Bar */}
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h3 className="font-semibold text-slate-700 mb-4">Complaints by Department</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={dashboard.department_stats}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="department_name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="total_complaints" fill="#2563eb" radius={[4, 4, 0, 0]} />
              <Bar dataKey="resolved" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Ward Stats Table */}
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <h3 className="font-semibold text-slate-700 mb-4">Ward-Level Statistics</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 px-4 font-medium text-slate-500">Ward</th>
                <th className="text-right py-3 px-4 font-medium text-slate-500">Total</th>
                <th className="text-right py-3 px-4 font-medium text-slate-500">Pending</th>
                <th className="text-right py-3 px-4 font-medium text-slate-500">Resolved</th>
                <th className="text-right py-3 px-4 font-medium text-slate-500">Resolution Rate</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.ward_stats?.filter(w => w.total_complaints > 0).map((ward) => (
                <tr key={ward.ward_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-3 px-4 font-medium text-slate-700">{ward.ward_name}</td>
                  <td className="text-right py-3 px-4">{ward.total_complaints}</td>
                  <td className="text-right py-3 px-4 text-yellow-600">{ward.pending}</td>
                  <td className="text-right py-3 px-4 text-green-600">{ward.resolved}</td>
                  <td className="text-right py-3 px-4">
                    <span className={`font-medium ${
                      ward.total_complaints > 0
                        ? (ward.resolved / ward.total_complaints) > 0.5 ? 'text-green-600' : 'text-red-500'
                        : 'text-slate-400'
                    }`}>
                      {ward.total_complaints > 0
                        ? `${Math.round((ward.resolved / ward.total_complaints) * 100)}%`
                        : 'N/A'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
          <p className="text-sm text-blue-600 font-medium">Complaints Today</p>
          <p className="text-3xl font-bold text-blue-800">{dashboard.complaints_today}</p>
        </div>
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5">
          <p className="text-sm text-indigo-600 font-medium">This Week</p>
          <p className="text-3xl font-bold text-indigo-800">{dashboard.complaints_this_week}</p>
        </div>
      </div>
    </div>
  );
}

function KPICard({ icon: Icon, label, value, color }) {
  const colorMap = {
    slate: 'bg-slate-50 text-slate-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    red: 'bg-red-50 text-red-700',
    purple: 'bg-purple-50 text-purple-700',
  };
  return (
    <div className={`rounded-xl p-4 ${colorMap[color]}`}>
      <Icon className="w-5 h-5 mb-2 opacity-60" />
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs opacity-70">{label}</p>
    </div>
  );
}
