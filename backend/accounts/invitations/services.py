from datetime import timedelta
import logging
import uuid
from typing import Tuple

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from companies.models import Company
from accounts.invitations.models import Invitation

logger = logging.getLogger(__name__)


def generate_invitation_email_html(
    company_name: str,
    inviter_name: str,
    worker_email: str,
    invite_url: str,
) -> str:
    """
    Generates clean inline responsive HTML for the worker onboarding invitation email.
    Omits any default/temporary passwords and directs the user straight to account activation.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invitation to join {company_name} on WorkHub</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
    .header {{ background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
    .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.025em; }}
    .header p {{ margin: 8px 0 0; font-size: 14px; opacity: 0.9; }}
    .content {{ padding: 32px 24px; }}
    .welcome-text {{ font-size: 16px; line-height: 1.6; color: #334155; margin-bottom: 24px; }}
    .info-card {{ background-color: #f1f5f9; border-left: 4px solid #4f46e5; border-radius: 6px; padding: 16px; margin: 24px 0; }}
    .info-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 6px; }}
    .info-value {{ font-size: 15px; font-weight: 600; color: #1e293b; }}
    .btn-container {{ text-align: center; margin: 32px 0 24px; }}
    .btn {{ display: inline-block; background-color: #4f46e5; color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 600; font-size: 15px; box-shadow: 0 2px 4px rgba(79, 70, 229, 0.3); }}
    .notice {{ font-size: 13px; color: #64748b; line-height: 1.5; border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 24px; }}
    .footer {{ background-color: #f8fafc; padding: 20px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>WorkHub Invitation</h1>
      <p>Multi-Tenant Workspace Platform</p>
    </div>
    <div class="content">
      <p class="welcome-text">
        Hello,<br><br>
        <strong>{inviter_name}</strong> has invited you to join the team at <strong>{company_name}</strong> on WorkHub.
      </p>

      <div class="info-card">
        <div class="info-title">Workspace Invitation</div>
        <div class="info-value">{company_name} &bull; {worker_email}</div>
      </div>

      <div class="btn-container">
        <a href="{invite_url}" class="btn" target="_blank">Accept Invitation & Set Password</a>
      </div>

      <p class="notice">
        <strong>Important:</strong> This onboarding link will expire in 48 hours. Simply click the button above to provide your name and set your secure password to access the workspace.
      </p>
    </div>
    <div class="footer">
      &copy; WorkHub Multi-Tenant Organization. If you were not expecting this invitation, you can safely ignore this email.
    </div>
  </div>
</body>
</html>
"""


def dispatch_worker_invitation(
    inviter: User,
    email: str,
    frontend_base_url: str = "",
) -> Tuple[Invitation, bool, str]:
    """
    Creates or refreshes an invitation for the worker, pre-allots a worker account,
    and dispatches the clean invitation email.
    """
    company: Company = inviter.company
    clean_email = email.strip().lower()
    token = uuid.uuid4().hex
    expires_at = timezone.now() + timedelta(hours=48)

    with transaction.atomic():
        # Remove any existing unaccepted invitation for this email in this company
        Invitation.objects.filter(company=company, email__iexact=clean_email, is_accepted=False).delete()

        # Create new invitation record
        invitation = Invitation.objects.create(
            email=clean_email,
            company=company,
            token=token,
            expires_at=expires_at,
        )

    # Determine frontend invitation URL
    base_url = (frontend_base_url or getattr(settings, "FRONTEND_URL", "http://localhost:5173")).rstrip("/")
    invite_url = f"{base_url}/accept-invite/{token}"

    inviter_name = inviter.get_full_name() or inviter.email
    email_subject = f"Invitation to join {company.name} on WorkHub"

    html_content = generate_invitation_email_html(
        company_name=company.name,
        inviter_name=inviter_name,
        worker_email=clean_email,
        invite_url=invite_url,
    )

    plain_text_content = (
        f"Hello,\n\n"
        f"You have been invited by {inviter_name} to join the team at {company.name} on WorkHub.\n\n"
        f"To complete your onboarding and choose your password, click the link below:\n\n"
        f"{invite_url}\n\n"
        f"This link expires in 48 hours.\n\n"
        f"Best regards,\nThe WorkHub Team"
    )

    msg = EmailMultiAlternatives(
        subject=email_subject,
        body=plain_text_content,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@workhub.internal"),
        to=[clean_email],
    )
    msg.attach_alternative(html_content, "text/html")

    email_sent = False
    status_message = ""
    try:
        msg.send(fail_silently=False)
        email_sent = True
        status_message = f"Invitation successfully dispatched to {clean_email}."
    except Exception as exc:
        logger.error(f"Failed to dispatch invitation email to {clean_email}: {exc}")
        email_sent = False
        status_message = f"Invitation record created, but email dispatch failed: {exc}"

    return invitation, email_sent, status_message
