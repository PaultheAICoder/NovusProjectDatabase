"""Microsoft Graph Email Service for feedback notification workflow.

Provides email reading capabilities via Microsoft Graph API:
- Sending notification emails when issues are resolved
- Reading reply emails from shared mailbox
- Testing Graph API connection

IMPORTANT: This service gracefully degrades when not configured.
All functions return empty results/False when Azure AD is not set up.

Configuration Required:
- AZURE_AD_TENANT_ID
- AZURE_AD_CLIENT_ID
- AZURE_AD_CLIENT_SECRET
- FEEDBACK_EMAIL (e.g., ai-coder@vital-enterprises.com)
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphEmailMessage:
    """Email message from Microsoft Graph."""

    id: str
    from_address: str
    subject: str
    body: str
    received_at: datetime
    in_reply_to: str | None
    references: str | None


class GraphEmailService:
    """Service for Microsoft Graph email operations."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: GraphServiceClient | None = None

    def is_configured(self) -> bool:
        """Check if Graph Email service is configured."""
        return self.settings.is_graph_email_configured

    def _get_client(self) -> GraphServiceClient | None:
        """Get or create Microsoft Graph client.

        Returns None if not configured, allowing graceful degradation.
        """
        if not self.is_configured():
            logger.warning("graph_email_not_configured")
            return None

        if self._client is None:
            credential = ClientSecretCredential(
                tenant_id=self.settings.azure_ad_tenant_id,
                client_id=self.settings.azure_ad_client_id,
                client_secret=self.settings.azure_ad_client_secret,
            )
            self._client = GraphServiceClient(
                credentials=credential,
                scopes=["https://graph.microsoft.com/.default"],
            )

        return self._client

    async def fetch_new_replies(self, since_date: datetime) -> list[GraphEmailMessage]:
        """Fetch new email replies since the given date.

        Only returns emails that are replies (have In-Reply-To or References headers).

        Args:
            since_date: Only fetch emails received after this date

        Returns:
            List of email messages, empty if service not configured
        """
        client = self._get_client()
        if not client:
            logger.debug("graph_email_not_configured", returning="empty_list")
            return []

        try:
            filter_date = since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            feedback_email = self.settings.feedback_email

            logger.info(
                "fetching_graph_emails",
                since=filter_date,
                mailbox=feedback_email,
            )

            # Fetch messages from the shared mailbox
            messages = await client.users.by_user_id(feedback_email).messages.get(
                request_configuration=lambda config: (
                    setattr(
                        config.query_parameters,
                        "filter",
                        f"receivedDateTime ge {filter_date}",
                    ),
                    setattr(
                        config.query_parameters,
                        "select",
                        [
                            "id",
                            "from",
                            "subject",
                            "body",
                            "receivedDateTime",
                            "internetMessageHeaders",
                        ],
                    ),
                    setattr(config.query_parameters, "orderby", ["receivedDateTime"]),
                )
            )

            if not messages or not messages.value:
                return []

            emails: list[GraphEmailMessage] = []

            for message in messages.value:
                # Extract In-Reply-To and References headers
                headers = message.internet_message_headers or []
                in_reply_to = None
                references = None

                for header in headers:
                    name_lower = (header.name or "").lower()
                    if name_lower == "in-reply-to":
                        in_reply_to = header.value
                    elif name_lower == "references":
                        references = header.value

                # Skip if not a reply
                if not in_reply_to and not references:
                    continue

                from_address = ""
                if message.from_ and message.from_.email_address:
                    from_address = message.from_.email_address.address or ""

                emails.append(
                    GraphEmailMessage(
                        id=message.id or "",
                        from_address=from_address,
                        subject=message.subject or "",
                        body=message.body.content if message.body else "",
                        received_at=message.received_date_time or datetime.now(tz=UTC),
                        in_reply_to=in_reply_to,
                        references=references,
                    )
                )

            logger.info("graph_emails_fetched", count=len(emails))
            return emails

        except Exception as e:
            logger.error(
                "graph_email_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
    ) -> bool:
        """Send an email via Microsoft Graph API.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: HTML body content

        Returns:
            True if sent successfully, False otherwise
        """
        client = self._get_client()
        if not client:
            logger.error("graph_email_not_configured", operation="send_email")
            return False

        recipients = [to] if isinstance(to, str) else to

        try:
            message = Message(
                subject=subject,
                body=ItemBody(
                    content_type=BodyType.Html,
                    content=body,
                ),
                to_recipients=[
                    Recipient(email_address=EmailAddress(address=email))
                    for email in recipients
                ],
            )

            request_body = SendMailPostRequestBody(
                message=message,
                save_to_sent_items=True,
            )

            await client.users.by_user_id(self.settings.feedback_email).send_mail.post(
                request_body
            )

            logger.info(
                "graph_email_sent",
                to=recipients,
                subject=subject[:50],
            )
            return True

        except Exception as e:
            logger.error(
                "graph_email_send_failed",
                error=str(e),
                error_type=type(e).__name__,
                to=recipients,
            )
            return False

    async def test_connection(self) -> bool:
        """Test Graph API connection.

        Returns:
            True if connection successful, False otherwise
        """
        client = self._get_client()
        if not client:
            logger.info("graph_email_connection_test", result="not_configured")
            return False

        try:
            # Try to fetch one message to test connection
            await client.users.by_user_id(self.settings.feedback_email).messages.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "top", 1),
                    setattr(config.query_parameters, "select", ["id"]),
                )
            )

            logger.info("graph_email_connection_test", result="success")
            return True

        except Exception as e:
            logger.error(
                "graph_email_connection_test",
                result="failed",
                error=str(e),
            )
            return False

    def get_status(self) -> dict:
        """Get configuration status for debugging."""
        return {
            "configured": self.is_configured(),
            "tenant_id": bool(self.settings.azure_ad_tenant_id),
            "client_id": bool(self.settings.azure_ad_client_id),
            "client_secret": bool(self.settings.azure_ad_client_secret),
            "feedback_email": self.settings.feedback_email or None,
        }
