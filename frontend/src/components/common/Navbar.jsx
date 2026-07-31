import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../utils/AuthContext';
import { Bot, Brain, LogOut, FileText, PlusCircle, LayoutDashboard, Shield } from 'lucide-react';

export default function Navbar() {
  const { user, logout, isAdmin, isOfficer, isCitizen } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <Brain className="w-8 h-8 text-brand-600" />
            <span className="text-xl font-bold text-slate-800">City Brain</span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center gap-1">
            {isCitizen && (
              <>
                <Link to="/submit"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                  <PlusCircle className="w-4 h-4" />
                  Report Issue
                </Link>
                <Link to="/my-complaints"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                  <FileText className="w-4 h-4" />
                  My Complaints
                </Link>
                <Link to="/assistant"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                  <Bot className="w-4 h-4" />
                  Assistant
                </Link>
              </>
            )}

            {isOfficer && (
              <Link to="/officer"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                <LayoutDashboard className="w-4 h-4" />
                Officer Dashboard
              </Link>
            )}

            {isAdmin && (
              <>
                <Link to="/admin"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                  <Shield className="w-4 h-4" />
                  Admin Dashboard
                </Link>
                <Link to="/officer"
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition">
                  <LayoutDashboard className="w-4 h-4" />
                  Officer View
                </Link>
              </>
            )}

            {/* User info + Logout */}
            <div className="flex items-center gap-3 ml-4 pl-4 border-l border-slate-200">
              <div className="text-right">
                <p className="text-sm font-medium text-slate-700">{user?.full_name}</p>
                <p className="text-xs text-slate-400 capitalize">{user?.role}</p>
              </div>
              <button
                onClick={handleLogout}
                className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
