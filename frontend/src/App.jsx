import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';

import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Profile from './pages/Profile';
import PublicDocuments from './pages/PublicDocuments';
import SearchResults from './pages/SearchResults';
import Settings from './pages/Settings';
import DocumentDetail from './pages/DocumentDetail';
import StudySpace from './pages/StudySpace';
import AdminDashboard from './pages/AdminDashboard';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const RequireAuth = () => {
  const location = useLocation();

  const [checking, setChecking] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const checkLogin = async () => {
      try {
        const res = await fetch(`${API_URL}/api/users/me`, {
          credentials: 'include',
          cache: 'no-store'
        });

        setIsLoggedIn(res.ok);
      } catch (error) {
        setIsLoggedIn(false);
      } finally {
        setChecking(false);
      }
    };

    checkLogin();
  }, []);

  if (checking) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        color: '#10b981',
        fontWeight: 700
      }}>
        Đang kiểm tra đăng nhập...
      </div>
    );
  }

  if (!isLoggedIn) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        {/* Public auth routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        {/* Guest allowed routes */}
        <Route element={<Layout />}>
          <Route path="/public-documents" element={<PublicDocuments />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/document/:id" element={<DocumentDetail />} />
        </Route>

        {/* Logged-in only routes */}
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/search" element={<SearchResults />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/study-space" element={<StudySpace />} />
            <Route path="/admin" element={<AdminDashboard />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
