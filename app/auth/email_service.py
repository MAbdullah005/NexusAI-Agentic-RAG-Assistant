import os

from dotenv import load_dotenv
from fastapi_mail import (
    FastMail,
    MessageSchema,
    ConnectionConfig,
)

load_dotenv()


# ============================================================
# Email Configuration
# ============================================================

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),

    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,

    USE_CREDENTIALS=True,
)


FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000"
)
if "8501" in FRONTEND_URL:
    FRONTEND_URL = "http://localhost:3000"

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
)


# ============================================================
# Send Verification Email
# ============================================================

async def send_verification_email(
    email: str,
    token: str
):
    verification_link = (
        f"{FRONTEND_URL}/verify-email"
        f"?token={token}"
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to NexusAI</title>
</head>
<body style="margin: 0; padding: 0; background-color: #fdf2f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #fdf2f8; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 520px; background-color: #ffffff; border-radius: 24px; border: 1px solid #fce7f3; box-shadow: 0 10px 30px rgba(236, 72, 153, 0.08); overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 36px 20px 36px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #ec4899; letter-spacing: -0.5px;">
                NexusAI
              </h1>
              <p style="margin: 4px 0 0 0; font-size: 13px; font-weight: 500; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">
                Intelligent Assistant
              </p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 10px 36px 28px 36px; text-align: left;">
              <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0f172a;">
                Welcome to NexusAI! 👋
              </h2>
              <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                Thank you for creating an account with us. We're excited to have you on board! With NexusAI, you can ask questions, explore documents, and discover meaningful insights across all your knowledge sources.
              </p>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                Please verify your email address to activate your account and start your journey:
              </p>
              <!-- Button -->
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 24px auto;">
                <tr>
                  <td align="center" style="border-radius: 9999px; background: linear-gradient(135deg, #ec4899 0%, #f43f5e 100%);">
                    <a href="{verification_link}" target="_blank" style="display: inline-block; padding: 12px 32px; font-size: 14px; font-weight: 600; color: #ffffff; text-decoration: none; border-radius: 9999px; letter-spacing: 0.2px;">
                      Verify Email
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin: 0 0 12px 0; font-size: 12px; line-height: 1.5; color: #94a3b8; text-align: center;">
                This link will safely expire in 15 minutes.
              </p>
              <div style="border-top: 1px solid #f1f5f9; margin-top: 24px; padding-top: 20px;">
                <p style="margin: 0 0 8px 0; font-size: 12px; line-height: 1.5; color: #94a3b8;">
                  If you didn't create a NexusAI account, no further action is needed—you can safely ignore this email.
                </p>
                <p style="margin: 16px 0 0 0; font-size: 13px; font-weight: 600; color: #334155;">
                  Warm regards,<br>
                  <span style="color: #ec4899;">The NexusAI Team</span>
                </p>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    message = MessageSchema(
        subject="Welcome to NexusAI — Verify Your Email",
        recipients=[email],
        body=html_content,
        subtype="html",
    )

    fm = FastMail(conf)

    await fm.send_message(message)


# ============================================================
# Send Password Reset Email
# ============================================================

async def send_reset_email(
    email: str,
    token: str
):
    # For now this points to the backend endpoint.
    # Later, when your Streamlit reset-password page exists,
    # we can change this to the frontend URL.

    reset_link = (
        f"{BACKEND_URL}/auth/reset-password"
        f"?token={token}"
    )

    message = MessageSchema(
        subject="Reset Your Password",
        recipients=[email],
        body=f"""
Hello,

We received a request to reset your password.

Click the link below to continue:

{reset_link}

This link will expire in 15 minutes.

If you did not request a password reset, you can safely ignore this email.

Regards,
YT + PDF Chat
""",
        subtype="plain",
    )

    fm = FastMail(conf)

    await fm.send_message(message)