import logging
import os

logger = logging.getLogger(__name__)

_SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@desd.local")
_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "DESD")


def send_email(to_email: str, subject: str, body: str, html: bool = False) -> bool:
    """Send an email via SendGrid. Returns True on success, False on failure."""
    if not _SENDGRID_API_KEY:
        # Fallback: log to console so OTP codes are still visible in dev
        logger.warning(
            "SENDGRID_API_KEY not set — printing email to log.\n"
            "TO: %s | SUBJECT: %s\n%s",
            to_email, subject, body,
        )
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, From, To, Subject, PlainTextContent, HtmlContent

        message = Mail(
            from_email=From(_FROM_EMAIL, _FROM_NAME),
            to_emails=To(to_email),
            subject=Subject(subject),
        )
        if html:
            message.content = [HtmlContent(body)]
        else:
            message.content = [PlainTextContent(body)]

        sg = SendGridAPIClient(_SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code not in (200, 201, 202):
            logger.error(
                "SendGrid returned unexpected status %s for email to %s",
                response.status_code, to_email,
            )
            return False

        logger.info("Email sent via SendGrid to %s (status %s)", to_email, response.status_code)
        return True

    except Exception as exc:
        logger.error("SendGrid error sending to %s: %s", to_email, exc)
        return False
