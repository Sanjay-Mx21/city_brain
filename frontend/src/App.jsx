import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './utils/AuthContext';

// Pages
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import CitizenHome from './pages/CitizenHome';
import SubmitComplaint from './pages/SubmitComplaint';
import MyComplaints from './pages/MyComplaints';
import TrackComplaint from './pages/TrackComplaint';
import OfficerDashboard from './pages/OfficerDashboard';
import AdminDashboard from './pages/AdminDashboard';
import AssistantPage from './pages/AssistantPage';
import Navbar from './components/common/Navbar';
import { dashboardPathForRole } from './utils/authRoutes';

function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, user, loading } = useAuth();

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" />;
  if (allowedRoles && !allowedRoles.includes(user?.role)) return <Navigate to="/" />;
  return children;
}

function AppRoutes() {
  const { isAuthenticated, user } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50">
      {isAuthenticated && <Navbar />}
      <Routes>
        {/* Public */}
        <Route path="/login" element={isAuthenticated ? <Navigate to={dashboardPathForRole(user?.role)} replace /> : <LoginPage />} />
        <Route path="/register" element={isAuthenticated ? <Navigate to={dashboardPathForRole(user?.role)} replace /> : <RegisterPage />} />
        <Route path="/track/:ticketId" element={<TrackComplaint />} />

        {/* Citizen */}
        <Route path="/" element={
          <ProtectedRoute>
            {user?.role === 'admin' ? <Navigate to="/admin" /> :
             user?.role === 'officer' ? <Navigate to="/officer" /> :
             <CitizenHome />}
          </ProtectedRoute>
        } />
        <Route path="/submit" element={
          <ProtectedRoute allowedRoles={['citizen']}>
            <SubmitComplaint />
          </ProtectedRoute>
        } />
        <Route path="/my-complaints" element={
          <ProtectedRoute allowedRoles={['citizen']}>
            <MyComplaints />
          </ProtectedRoute>
        } />
        <Route path="/assistant" element={
          <ProtectedRoute allowedRoles={['citizen']}>
            <AssistantPage />
          </ProtectedRoute>
        } />

        {/* Officer */}
        <Route path="/officer" element={
          <ProtectedRoute allowedRoles={['officer', 'admin']}>
            <OfficerDashboard />
          </ProtectedRoute>
        } />

        {/* Admin */}
        <Route path="/admin" element={
          <ProtectedRoute allowedRoles={['admin']}>
            <AdminDashboard />
          </ProtectedRoute>
        } />
      </Routes>
      <Toaster position="top-right" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
