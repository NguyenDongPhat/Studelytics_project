import React, { useEffect, useState } from 'react';
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import {
  ArrowRight,
  LogIn,
  UserRound,
} from 'lucide-react';
import '../assets/css/login.css';

const Login = () => {
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  const location = useLocation();

  const API_URL = (
    import.meta.env.VITE_API_URL || 'http://localhost:8000'
  ).replace(/\/+$/, '');

  const redirectTo = location.state?.from?.pathname || '/dashboard';

  // Chuyển lỗi từ FastAPI thành chuỗi để React hiển thị an toàn.
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
            return 'Dữ liệu không hợp lệ.';
          }

          const field = Array.isArray(item.loc)
            ? item.loc
                .filter((part) => part !== 'body')
                .join('.')
            : '';

          const message = item.msg || 'Dữ liệu không hợp lệ.';

          return field ? `${field}: ${message}` : message;
        })
        .join('; ');
    }

    if (detail && typeof detail === 'object') {
      return (
        detail.message ||
        detail.msg ||
        'Thông tin đăng nhập không hợp lệ.'
      );
    }

    return 'Đăng nhập thất bại. Vui lòng kiểm tra email và mật khẩu.';
  };

  // Hiển thị lỗi OAuth nếu backend chuyển hướng về frontend kèm mã lỗi.
  useEffect(() => {
    const oauthError = searchParams.get('oauth_error');

    if (!oauthError) {
      return;
    }

    const messages = {
      google_denied: 'Bạn đã hủy đăng nhập bằng Google.',
      invalid_state: 'Phiên đăng nhập Google không hợp lệ. Vui lòng thử lại.',
      missing_code: 'Google không trả về mã xác thực. Vui lòng thử lại.',
      no_access_token: 'Không lấy được access token từ Google.',
      no_email: 'Không lấy được email từ tài khoản Google.',
      banned: 'Tài khoản của bạn đã bị khóa.',
      google_failed: 'Đăng nhập Google thất bại. Vui lòng thử lại.',
    };

    setError(
      messages[oauthError] || 'Đăng nhập Google thất bại. Vui lòng thử lại.'
    );
  }, [searchParams]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    const normalizedEmail = email.trim();

    if (!normalizedEmail || !password) {
      setError('Vui lòng nhập email và mật khẩu.');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          email: normalizedEmail,
          password,
        }),
      });

      // Đọc response an toàn kể cả khi body không phải JSON.
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

      // Backend cần thiết lập cookie hoặc cơ chế xác thực tương ứng.
      navigate(redirectTo, { replace: true });
    } catch (err) {
      console.error('Login request failed:', err);

      setError(
        'Không thể kết nối tới máy chủ. Vui lòng kiểm tra backend và cấu hình API.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleContinueAsGuest = () => {
    navigate('/public-documents');
  };

  const handleGoogleLogin = () => {
    // Chỉ hoạt động nếu backend đã triển khai endpoint OAuth này.
    window.location.href = `${API_URL}/api/auth/google/login`;
  };

  const handleFacebookLogin = () => {
    setError('Đăng nhập bằng Facebook hiện chưa được triển khai.');
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
          <h2>Đăng nhập</h2>
          <p>Chào mừng trở lại với Studelytics</p>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <div className="auth-social-group">
            <button
              type="button"
              className="auth-social-btn"
              onClick={handleGoogleLogin}
            >
              <span className="auth-provider-icon google">G</span>
              Đăng nhập bằng Google
            </button>

            <button
              type="button"
              className="auth-social-btn"
              onClick={handleFacebookLogin}
            >
              <span className="auth-provider-icon facebook">f</span>
              Đăng nhập bằng Facebook
            </button>
          </div>

          <div className="auth-divider">
            <span>hoặc</span>
          </div>

          <form onSubmit={handleLogin}>
            <div className="auth-input-group">
              <label htmlFor="login-email">Email</label>

              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Nhập email của bạn"
                autoComplete="email"
                required
              />
            </div>

            <div className="auth-input-group">
              <div className="auth-label-row">
                <label htmlFor="login-password">Mật khẩu</label>

                <Link to="/forgot-password">
                  Quên mật khẩu?
                </Link>
              </div>

              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu"
                autoComplete="current-password"
                required
              />
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                'Đang xử lý...'
              ) : (
                <>
                  <LogIn size={17} />
                  Đăng nhập
                </>
              )}
            </button>
          </form>

          <button
            type="button"
            className="auth-guest-btn"
            onClick={handleContinueAsGuest}
          >
            <UserRound size={17} />
            Tiếp tục với tư cách khách
            <ArrowRight size={16} />
          </button>

          <Link to="/register" className="auth-link">
            Chưa có tài khoản? Đăng ký ngay
          </Link>
        </section>
      </main>
    </div>
  );
};

export default Login;