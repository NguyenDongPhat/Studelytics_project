import React, { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  ChevronDown,
  LogOut,
  Search,
  Settings,
  ShieldCheck,
  UserCircle2
} from 'lucide-react';
import '../assets/css/style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Layout = () => {
  const navigate = useNavigate();
  const dropdownRef = useRef(null);

  const [user, setUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  const logoutAndRedirect = async (message) => {
    if (message) alert(message);

    try {
      await fetch(`${API_URL}/api/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('Lỗi đăng xuất:', error);
    }

    setUser({ username: 'Khách', isGuest: true });
    setShowDropdown(false);
    navigate('/login');
  };

  const checkAccountStatus = async (silent = false) => {
    try {
      const res = await fetch(`${API_URL}/api/users/me`, {
        credentials: 'include',
        cache: 'no-store'
      });

      if (res.status === 403) {
        await logoutAndRedirect('Tài khoản của bạn đã bị khóa.');
        return;
      }

      if (res.status === 401) {
        setUser({ username: 'Khách', isGuest: true });
        return;
      }

      if (!res.ok) {
        if (!silent) setUser({ username: 'Khách', isGuest: true });
        return;
      }

      const data = await res.json();
      if (data && data.id) setUser(data);
    } catch (error) {
      console.error('Lỗi kiểm tra tài khoản:', error);
      if (!silent) setUser({ username: 'Khách', isGuest: true });
    }
  };

  useEffect(() => {
    checkAccountStatus(false);

    const interval = setInterval(() => {
      checkAccountStatus(true);
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logoutAndRedirect();
  };

  const handleSearch = (e) => {
    e.preventDefault();

    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  };

  if (!user) {
    return <div className="layout-loading">Đang tải...</div>;
  }

  return (
    <div className="app-layout">
      <header className="minimal-navbar">
        <Link to="/dashboard" className="studelytics-logo">
          Studelytics
        </Link>

        <div className="minimal-nav-right">
          <form onSubmit={handleSearch} className="minimal-search-form">
            <div className="minimal-search-box">
              <Search size={16} />
              <input
                type="text"
                placeholder="Tìm kiếm tài liệu..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <button type="submit" className="minimal-search-btn">
              Tìm
            </button>
          </form>

          <nav className="minimal-links" aria-label="Điều hướng chính">
            <NavLink to="/dashboard" className="minimal-link">Dashboard</NavLink>
            <NavLink to="/chat" className="minimal-link">AI Chat</NavLink>
            <NavLink to="/study-space" className="minimal-link">Góc học tập</NavLink>
            <NavLink to="/public-documents" className="minimal-link">Thư viện</NavLink>

            {user?.role === 2 && (
              <NavLink to="/admin" className="minimal-link minimal-admin-link">
                Admin
              </NavLink>
            )}
          </nav>

          <div className="account-dropdown" ref={dropdownRef}>
            <button
              type="button"
              className={`account-trigger ${showDropdown ? 'active' : ''}`}
              onClick={() => setShowDropdown(prev => !prev)}
            >
              <span>
                {user.isGuest ? 'Chế độ khách' : <>Chào, <b>{user.username}</b></>}
              </span>

              <ChevronDown
                size={15}
                className={showDropdown ? 'rotated' : ''}
              />
            </button>

            {showDropdown && (
              <div className="account-menu">
                <div className="account-menu-header">
                  <div className="account-avatar">
                    {user.isGuest ? 'K' : user.username?.charAt(0)?.toUpperCase()}
                  </div>

                  <div>
                    <strong>{user.isGuest ? 'Khách truy cập' : user.username}</strong>
                    <span>{user.isGuest ? 'Bạn chưa đăng nhập' : 'Tài khoản Studelytics'}</span>
                  </div>
                </div>

                {!user.isGuest && (
                  <>
                    <Link
                      to="/profile"
                      className="account-menu-item"
                      onClick={() => setShowDropdown(false)}
                    >
                      <UserCircle2 size={17} />
                      Hồ sơ cá nhân
                    </Link>

                    <Link
                      to="/settings"
                      className="account-menu-item"
                      onClick={() => setShowDropdown(false)}
                    >
                      <Settings size={17} />
                      Cài đặt hệ thống
                    </Link>
                  </>
                )}

                {user?.role === 2 && (
                  <Link
                    to="/admin"
                    className="account-menu-item admin"
                    onClick={() => setShowDropdown(false)}
                  >
                    <ShieldCheck size={17} />
                    Trang quản trị
                  </Link>
                )}

                <button type="button" className="account-menu-item danger" onClick={handleLogout}>
                  <LogOut size={17} />
                  {user.isGuest ? 'Đăng nhập' : 'Đăng xuất'}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main-content" className="app-main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
