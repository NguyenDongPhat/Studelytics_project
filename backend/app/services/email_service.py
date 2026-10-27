import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER or "no-reply@lumina-ai.local")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Lumina AI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def _is_smtp_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def _send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    if not _is_smtp_configured():
        print("\n========== EMAIL DEBUG MODE ==========")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(text_body or html_body)
        print("======================================\n")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email

    if text_body:
        message.attach(MIMEText(text_body, "plain", "utf-8"))

    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], message.as_string())
        return True
    except Exception as exc:
        print(f"⚠️ Lỗi gửi email tới {to_email}: {exc}")
        return False


def send_welcome_email(to_email: str, username: str):
    subject = "Chào mừng bạn đến với Lumina AI"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #0f172a;">
        <h2>Chào mừng {username} đến với Lumina AI!</h2>
        <p>Tài khoản của bạn đã được tạo thành công.</p>
        <p>Bạn có thể bắt đầu upload tài liệu, hỏi đáp với AI, tạo flashcard và khám phá thư viện cộng đồng.</p>
        <p>
            <a href="{FRONTEND_URL}/login"
               style="display:inline-block;background:#10b981;color:white;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700;">
               Đăng nhập ngay
            </a>
        </p>
        <p style="color:#64748b;font-size:13px;">Lumina AI</p>
    </div>
    """

    text = f"""Chào mừng {username} đến với Lumina AI!

Tài khoản của bạn đã được tạo thành công.
Đăng nhập tại: {FRONTEND_URL}/login
"""

    return _send_email(to_email, subject, html, text)


def send_password_reset_email(to_email: str, username: str, token: str):
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    subject = "Đặt lại mật khẩu Lumina AI"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #0f172a;">
        <h2>Đặt lại mật khẩu</h2>
        <p>Xin chào {username},</p>
        <p>Bạn vừa yêu cầu đặt lại mật khẩu cho tài khoản Lumina AI.</p>
        <p>Nhấn nút bên dưới để tạo mật khẩu mới. Link có hiệu lực trong một khoảng thời gian ngắn.</p>
        <p>
            <a href="{reset_link}"
               style="display:inline-block;background:#10b981;color:white;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700;">
               Đặt lại mật khẩu
            </a>
        </p>
        <p>Nếu nút không hoạt động, hãy copy link này vào trình duyệt:</p>
        <p style="word-break:break-all;color:#047857;">{reset_link}</p>
        <p style="color:#64748b;font-size:13px;">Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
    </div>
    """

    text = f"""Xin chào {username},

Bạn vừa yêu cầu đặt lại mật khẩu cho tài khoản Lumina AI.
Mở link sau để tạo mật khẩu mới:
{reset_link}

Nếu bạn không yêu cầu, hãy bỏ qua email này.
"""

    return _send_email(to_email, subject, html, text)
