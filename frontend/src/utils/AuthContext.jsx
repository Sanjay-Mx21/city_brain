/**
 * City Brain — Auth Context
 * Global authentication state management.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('cb_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('cb_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {}
    }
    setLoading(false);
  }, []);

  const login = (tokenStr, userData) => {
    localStorage.setItem('cb_token', tokenStr);
    localStorage.setItem('cb_user', JSON.stringify(userData));
    setToken(tokenStr);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('cb_token');
    localStorage.removeItem('cb_user');
    setToken(null);
    setUser(null);
  };

  const isAuthenticated = !!token && !!user;
  const isAdmin = user?.role === 'admin';
  const isOfficer = user?.role === 'officer';
  const isCitizen = user?.role === 'citizen';

  return (
    <AuthContext.Provider value={{
      user, token, loading, login, logout,
      isAuthenticated, isAdmin, isOfficer, isCitizen,
    }}>
      {children}
    </AuthContext.Provider>
  );
}
