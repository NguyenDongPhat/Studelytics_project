import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../assets/css/login.css';

const Register = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const API_URL = (
    import.meta.env.VITE_API_URL || 'http://localhost:8000'
  ).replace(/\/+$/, '');

  const navigate = useNavigate();

  // Chuyển lỗi FastAPI thành chuỗi để React hiển thị an toàn.
  const getErrorMessage = (detail) => {
    if (typeof detail === 'string') {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') {
            return item;
          }

          if (!item || typeof item !== 'object') {
            return 'Dữ liệu không hợp lệ';
          }

          const location = Array.isArray(item.loc)
            ? item.loc
                .filter((part) => part !== 'body')
                .join('.')
            : '';

          const message = item.msg || 'Dữ liệu không hợp lệ';

          // Ví dụ: username: Field required
          return location ? `${location}: ${message}` : message;
        })
        .join('; ');
    }

    if (detail && typeof detail === 'object') {
      return detail.message || detail.msg || 'Yêu cầu không hợp lệ.';
    }

    return 'Có lỗi xảy ra khi đăng ký tài khoản.';
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');

    const normalizedUsername = username.trim();
    const normalizedEmail = email.trim();

    if (!normalizedUsername || !normalizedEmail || !password) {
      setError('Vui lòng nhập đầy đủ tên hiển thị, email và mật khẩu.');
      return;
    }

    if (normalizedUsername.length < 3) {
      setError('Tên hiển thị phải có ít nhất 3 ký tự.');
      return;
    }

    if (password.length < 8) {
      setError('Mật khẩu phải có ít nhất 8 ký tự.');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          username: normalizedUsername,
          email: normalizedEmail,
          password,
        }),
      });

      // Đọc response an toàn, kể cả khi backend không trả JSON hợp lệ.
      const responseText = await response.text();
      let data = {};

      if (responseText) {
        try {
          data = JSON.parse(responseText);
        } catch {
          data = { detail: responseText };
        }
      }

      if (!response.ok) {
        setError(
          getErrorMessage(data.detail ?? data.message)
        );
        return;
      }

      alert('Đăng ký thành công! Vui lòng đăng nhập.');
      navigate('/login');
    } catch (err) {
      console.error('Register request failed:', err);

      setError(
        'Không thể kết nối tới máy chủ. Vui lòng kiểm tra backend và cấu hình API.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <header className="auth-navbar">
        <Link to="/" className="auth-logo">
          Studelytics
        </Link>

        <Link to="/" className="auth-nav-link">
          Trang chủ
        </Link>
      </header>

      <main className="auth-container">
        <section className="auth-card">
          <h2>Đăng ký</h2>
          <p>Tạo tài khoản Studelytics mới</p>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleRegister}>
            <div className="auth-input-group">
              <label htmlFor="register-username">
                Tên hiển thị
              </label>

              <input
                id="register-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Nhập tên của bạn"
                minLength={3}
                maxLength={50}
                autoComplete="username"
                required
              />
            </div>

            <div className="auth-input-group">
              <label htmlFor="register-email">
                Email
              </label>

              <input
                id="register-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Nhập email"
                maxLength={255}
                autoComplete="email"
                required
              />
            </div>

            <div className="auth-input-group">
              <label htmlFor="register-password">
                Mật khẩu
              </label>

              <input
                id="register-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ít nhất 8 ký tự"
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? 'Đang xử lý...' : 'Đăng ký tài khoản'}
            </button>
          </form>

          <Link to="/login" className="auth-link">
            Đã có tài khoản? Đăng nhập
          </Link>
        </section>
      </main>
    </div>
  );
};

export default Register;