#!/usr/bin/env python3
"""
Test reading emails via Softeria MS365 MCP Server
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_env():
    """Load .env file"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


async def main():
    """Test reading emails via MCP server"""
    load_env()

    client_id = os.environ.get("MS365_CLIENT_ID")
    tenant_id = os.environ.get("MS365_TENANT_ID")
    client_secret = os.environ.get("MS365_CLIENT_SECRET")

    logger.info("=" * 80)
    logger.info("Testing Email Reading via Softeria MS365 MCP Server")
    logger.info("=" * 80)

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Create server parameters
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@softeria/ms-365-mcp-server"],
            env={
                "MS365_MCP_CLIENT_ID": client_id,
                "MS365_MCP_TENANT_ID": tenant_id,
                "MS365_MCP_CLIENT_SECRET": client_secret,
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("✅ Connected to MCP server")

                # Verify login
                logger.info("\n" + "=" * 80)
                logger.info("Step 1: Verify Login")
                logger.info("=" * 80)

                result = await session.call_tool("verify-login", arguments={})
                logger.info("Login status:")
                for content in result.content:
                    if hasattr(content, "text"):
                        login_data = json.loads(content.text)
                        logger.info(
                            f"  User: {login_data.get('userData', {}).get('displayName')}"
                        )
                        logger.info(
                            f"  Email: {login_data.get('userData', {}).get('userPrincipalName')}"
                        )

                # List recent emails
                logger.info("\n" + "=" * 80)
                logger.info("Step 2: List Recent Emails (10 messages)")
                logger.info("=" * 80)

                result = await session.call_tool(
                    "list-mail-messages", arguments={"top": 10}
                )

                logger.info("\nEmail results:")
                for content in result.content:
                    if hasattr(content, "text"):
                        try:
                            emails = json.loads(content.text)
                            if isinstance(emails, dict) and "value" in emails:
                                messages = emails["value"]
                                logger.info(
                                    f"\n✅ Found {len(messages)} emails:\n"
                                )

                                for idx, msg in enumerate(messages, 1):
                                    logger.info(f"📧 Email #{idx}")
                                    logger.info("-" * 80)

                                    # Read status
                                    is_read = msg.get("isRead", False)
                                    status = "READ" if is_read else "UNREAD"
                                    logger.info(f"  Status: [{status}]")

                                    # Subject
                                    subject = msg.get(
                                        "subject", "(no subject)"
                                    )
                                    logger.info(f"  Subject: {subject}")

                                    # From
                                    from_field = msg.get("from", {})
                                    if (
                                        from_field
                                        and "emailAddress" in from_field
                                    ):
                                        email_addr = from_field[
                                            "emailAddress"
                                        ]
                                        sender_name = email_addr.get(
                                            "name", "Unknown"
                                        )
                                        sender_email = email_addr.get(
                                            "address", "unknown@unknown.com"
                                        )
                                        logger.info(
                                            f"  From: {sender_name} <{sender_email}>"
                                        )

                                    # Date
                                    received = msg.get("receivedDateTime", "")
                                    if received:
                                        logger.info(f"  Date: {received}")

                                    # Preview
                                    preview = msg.get("bodyPreview", "")
                                    if preview:
                                        preview_text = preview[:150]
                                        if len(preview) > 150:
                                            preview_text += "..."
                                        logger.info(
                                            f"  Preview: {preview_text}"
                                        )

                                    logger.info("")

                                logger.info("=" * 80)
                                logger.info(
                                    f"✅ Successfully read {len(messages)} emails via MCP server!"
                                )
                                logger.info("=" * 80)
                            else:
                                logger.info(f"Response: {content.text}")
                        except json.JSONDecodeError:
                            logger.info(
                                f"Response (not JSON): {content.text}"
                            )

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.exception("Full traceback:")
        return 1

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("⚠️  Interrupted")
        sys.exit(130)
