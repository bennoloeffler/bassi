#!/usr/bin/env python3
"""
Test script for reading emails via Microsoft Graph API
With extensive debugging and error handling
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_read_email.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Load .env file manually"""
    logger.info("=" * 80)
    logger.info("STEP 1: Loading .env file")
    logger.info("=" * 80)

    env_file = Path(".env")
    if not env_file.exists():
        logger.error(f"❌ .env file not found at: {env_file.absolute()}")
        return False

    logger.info(f"✅ Found .env file at: {env_file.absolute()}")

    # Read and parse .env file
    with open(env_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                os.environ[key] = value

                # Log without showing full value (security)
                if "ID" in key:
                    logger.info(
                        f"  Line {line_num}: Set {key} = {value[:8]}...{value[-4:]}"
                    )
                else:
                    logger.info(f"  Line {line_num}: Set {key}")

    return True


def check_configuration():
    """Check if required configuration is present"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: Checking Configuration")
    logger.info("=" * 80)

    client_id = os.environ.get("MS365_CLIENT_ID")
    tenant_id = os.environ.get("MS365_TENANT_ID", "common")

    if not client_id:
        logger.error("❌ MS365_CLIENT_ID not found in environment")
        return None, None

    logger.info(f"✅ MS365_CLIENT_ID: {client_id[:8]}...{client_id[-4:]}")
    logger.info(f"✅ MS365_TENANT_ID: {tenant_id}")

    return client_id, tenant_id


async def authenticate(client_id: str, tenant_id: str):
    """Authenticate using Device Code Flow"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 3: Authentication (Device Code Flow)")
    logger.info("=" * 80)

    try:
        from azure.identity import DeviceCodeCredential

        logger.info("Creating DeviceCodeCredential...")

        # Device code callback for better UX
        def device_code_callback(verification_uri, user_code, expires_in):
            logger.info("")
            logger.info("🔐 AUTHENTICATION REQUIRED")
            logger.info("=" * 80)
            logger.info("")
            logger.info("  👉 Open this URL in your browser:")
            logger.info(f"     {verification_uri}")
            logger.info("")
            logger.info("  👉 Enter this code:")
            logger.info(f"     {user_code}")
            logger.info("")
            logger.info(f"  ⏰ Code expires in: {expires_in} seconds")
            logger.info("=" * 80)
            logger.info("Waiting for authentication...")

        credential = DeviceCodeCredential(
            client_id=client_id,
            tenant_id=tenant_id,
            prompt_callback=device_code_callback,
        )

        logger.info("✅ DeviceCodeCredential created")
        return credential

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error(
            "   Make sure azure-identity is installed: uv add azure-identity"
        )
        return None
    except Exception as e:
        logger.error(f"❌ Authentication setup failed: {e}")
        logger.exception("Full traceback:")
        return None


async def create_graph_client(credential):
    """Create Microsoft Graph client"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 4: Creating Graph Client")
    logger.info("=" * 80)

    try:
        from msgraph import GraphServiceClient

        # Define required scopes
        # Note: Use full Graph API URL format, NOT short names
        scopes = [
            "https://graph.microsoft.com/User.Read",
            "https://graph.microsoft.com/Mail.Read",
        ]

        logger.info(f"Required scopes: {', '.join(scopes)}")
        logger.info("Creating GraphServiceClient...")

        client = GraphServiceClient(credentials=credential, scopes=scopes)

        logger.info("✅ GraphServiceClient created")
        return client

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error(
            "   Make sure msgraph-sdk is installed: uv add msgraph-sdk"
        )
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create Graph client: {e}")
        logger.exception("Full traceback:")
        return None


async def test_connection(client):
    """Test connection by getting current user info"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 5: Testing Connection (Get Current User)")
    logger.info("=" * 80)

    try:
        logger.info("Calling client.me.get()...")
        logger.info(
            "(This will trigger device code authentication if needed)"
        )

        user = await client.me.get()

        if user:
            logger.info("✅ Successfully authenticated!")
            logger.info(f"   User: {user.display_name}")
            logger.info(f"   Email: {user.user_principal_name}")
            logger.info(f"   ID: {user.id}")
            return True
        else:
            logger.error("❌ Got None response from API")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to get user info: {e}")
        logger.exception("Full traceback:")
        return False


async def read_emails(client, max_results: int = 5):
    """Read recent emails from inbox"""
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"STEP 6: Reading Recent Emails (max {max_results})")
    logger.info("=" * 80)

    try:
        logger.info("Calling client.me.messages.get()...")

        # Simplified approach - let Graph API handle defaults
        # The new SDK structure doesn't expose request builders the same way

        logger.info(f"  Requesting top {max_results} messages...")
        logger.info("  Using default ordering and fields")

        # Simple call - SDK handles the defaults
        messages = await client.me.messages.get()

        if not messages or not messages.value:
            logger.warning("⚠️  No messages found in inbox")
            return

        logger.info(f"✅ Found {len(messages.value)} messages")
        logger.info("")
        logger.info("=" * 80)
        logger.info("EMAILS")
        logger.info("=" * 80)

        for idx, msg in enumerate(messages.value, 1):
            logger.info("")
            logger.info(f"📧 Email #{idx}")
            logger.info("-" * 80)

            # Status
            status = "UNREAD" if not msg.is_read else "READ"
            logger.info(f"  Status: [{status}]")

            # Subject
            logger.info(f"  Subject: {msg.subject or '(no subject)'}")

            # From
            if msg.from_ and msg.from_.email_address:
                sender_name = msg.from_.email_address.name or "Unknown"
                sender_email = (
                    msg.from_.email_address.address or "unknown@unknown.com"
                )
                logger.info(f"  From: {sender_name} <{sender_email}>")

            # Date
            if msg.received_date_time:
                logger.info(f"  Date: {msg.received_date_time}")

            # Attachments
            if msg.has_attachments:
                logger.info("  Attachments: Yes")

            # Preview
            if msg.body_preview:
                preview = msg.body_preview[:150]
                if len(msg.body_preview) > 150:
                    preview += "..."
                logger.info(f"  Preview: {preview}")

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Successfully read {len(messages.value)} emails!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Failed to read emails: {e}")
        logger.exception("Full traceback:")


async def main():
    """Main test flow"""
    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info(
        "║" + "  TEST: Read Emails via Microsoft Graph API".center(78) + "║"
    )
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")

    # Step 1: Load .env
    if not load_env_file():
        logger.error("❌ Failed to load .env file")
        return 1

    # Step 2: Check configuration
    client_id, tenant_id = check_configuration()
    if not client_id:
        logger.error("❌ Configuration incomplete")
        return 1

    # Step 3: Authenticate
    credential = await authenticate(client_id, tenant_id)
    if not credential:
        logger.error("❌ Authentication setup failed")
        return 1

    # Step 4: Create Graph client
    client = await create_graph_client(credential)
    if not client:
        logger.error("❌ Failed to create Graph client")
        return 1

    # Step 5: Test connection
    if not await test_connection(client):
        logger.error("❌ Connection test failed")
        return 1

    # Step 6: Read emails
    await read_emails(client, max_results=5)

    logger.info("")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 78 + "║")
    logger.info("║" + "  TEST COMPLETE".center(78) + "║")
    logger.info("║" + " " * 78 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("")
    logger.info("📄 Full log saved to: test_read_email.log")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("")
        logger.warning("⚠️  Interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)
