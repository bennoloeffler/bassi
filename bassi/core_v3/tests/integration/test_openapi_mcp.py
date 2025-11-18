"""Tests for openapi_mcp.py - OpenAPI to MCP server converter."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCreateMCPFromOpenAPI:
    """Test create_mcp_from_openapi function."""

    @pytest.mark.asyncio
    async def test_create_public_api_no_auth(self):
        """Test creating MCP from public API without authentication."""
        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        mock_spec = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_spec
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("bassi.core_v3.openapi_mcp.FastMCP") as mock_fastmcp,
        ):
            # Mock httpx.AsyncClient() context manager
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Mock FastMCP.from_openapi()
            mock_server = MagicMock(name="test_server")
            mock_fastmcp.from_openapi.return_value = mock_server

            result = await create_mcp_from_openapi(
                name="test-api",
                openapi_url="https://api.example.com/openapi.json",
            )

            assert result == mock_server
            mock_fastmcp.from_openapi.assert_called_once()
            call_kwargs = mock_fastmcp.from_openapi.call_args.kwargs
            assert call_kwargs["name"] == "test-api"
            assert call_kwargs["openapi_spec"] == mock_spec

    @pytest.mark.asyncio
    async def test_create_with_bearer_token(self):
        """Test creating MCP with bearer token authentication."""
        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        mock_spec = {"openapi": "3.0.0"}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_spec
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("bassi.core_v3.openapi_mcp.FastMCP") as mock_fastmcp,
        ):
            # Mock temporary client for fetching spec
            mock_temp_client = MagicMock()
            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock()
            mock_temp_client.get = AsyncMock(return_value=mock_response)

            # Mock authenticated client for API calls
            mock_auth_client = MagicMock(name="auth_client")

            mock_client_class.side_effect = [
                mock_temp_client,
                mock_auth_client,
            ]

            mock_server = MagicMock()
            mock_fastmcp.from_openapi.return_value = mock_server

            result = await create_mcp_from_openapi(
                name="github",
                openapi_url="https://api.github.com/openapi.json",
                auth_token="ghp_test123",
            )

            assert result == mock_server

            # Verify authenticated client was created with Bearer token
            auth_call = mock_client_class.call_args_list[1]
            assert "headers" in auth_call.kwargs
            headers = auth_call.kwargs["headers"]
            assert headers["Authorization"] == "Bearer ghp_test123"

    @pytest.mark.asyncio
    async def test_create_with_api_key(self):
        """Test creating MCP with API key authentication."""
        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        mock_spec = {"openapi": "3.0.0"}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_spec
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("bassi.core_v3.openapi_mcp.FastMCP") as mock_fastmcp,
        ):
            mock_temp_client = MagicMock()
            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock()
            mock_temp_client.get = AsyncMock(return_value=mock_response)

            mock_auth_client = MagicMock()
            mock_client_class.side_effect = [
                mock_temp_client,
                mock_auth_client,
            ]

            mock_server = MagicMock()
            mock_fastmcp.from_openapi.return_value = mock_server

            result = await create_mcp_from_openapi(
                name="weatherapi",
                openapi_url="https://weatherapi.com/openapi.json",
                api_key="abc123",
                api_key_header="X-API-Key",
            )

            assert result == mock_server

            # Verify API key header
            auth_call = mock_client_class.call_args_list[1]
            headers = auth_call.kwargs["headers"]
            assert headers["X-API-Key"] == "abc123"

    @pytest.mark.asyncio
    async def test_create_with_custom_api_key_header(self):
        """Test creating MCP with custom API key header name."""
        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        mock_spec = {"openapi": "3.0.0"}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_spec
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("bassi.core_v3.openapi_mcp.FastMCP") as mock_fastmcp,
        ):
            mock_temp_client = MagicMock()
            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock()
            mock_temp_client.get = AsyncMock(return_value=mock_response)

            mock_auth_client = MagicMock()
            mock_client_class.side_effect = [
                mock_temp_client,
                mock_auth_client,
            ]

            mock_server = MagicMock()
            mock_fastmcp.from_openapi.return_value = mock_server

            await create_mcp_from_openapi(
                name="custom",
                openapi_url="https://api.example.com/openapi.json",
                api_key="key123",
                api_key_header="Authorization",
            )

            # Verify custom header name
            auth_call = mock_client_class.call_args_list[1]
            headers = auth_call.kwargs["headers"]
            assert headers["Authorization"] == "key123"

    @pytest.mark.asyncio
    async def test_create_http_error(self):
        """Test error handling when fetching OpenAPI spec fails."""
        import httpx

        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_temp_client = MagicMock()

            # Make __aexit__ propagate exceptions properly
            async def mock_aexit(exc_type, exc_val, exc_tb):
                # Return False to propagate exception, or None (implicit False)
                return False

            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock(side_effect=mock_aexit)
            mock_temp_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404 Not Found",
                    request=MagicMock(),
                    response=MagicMock(status_code=404),
                )
            )
            mock_client_class.return_value = mock_temp_client

            with pytest.raises(httpx.HTTPStatusError):
                await create_mcp_from_openapi(
                    name="test",
                    openapi_url="https://api.example.com/invalid.json",
                )

    @pytest.mark.asyncio
    async def test_create_timeout(self):
        """Test timeout when fetching OpenAPI spec."""
        import httpx

        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_temp_client = MagicMock()

            # Make __aexit__ propagate exceptions properly
            async def mock_aexit(exc_type, exc_val, exc_tb):
                # Return False to propagate exception, or None (implicit False)
                return False

            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock(side_effect=mock_aexit)
            mock_temp_client.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_client_class.return_value = mock_temp_client

            with pytest.raises(httpx.TimeoutException):
                await create_mcp_from_openapi(
                    name="test",
                    openapi_url="https://api.example.com/slow.json",
                )

    @pytest.mark.asyncio
    async def test_create_invalid_json(self):
        """Test error handling when OpenAPI spec is invalid JSON."""
        from bassi.core_v3.openapi_mcp import create_mcp_from_openapi

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError(
            "Invalid JSON", "", 0
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_temp_client = MagicMock()

            # Make __aexit__ propagate exceptions properly
            async def mock_aexit(exc_type, exc_val, exc_tb):
                # Return False to propagate exception, or None (implicit False)
                return False

            mock_temp_client.__aenter__ = AsyncMock(
                return_value=mock_temp_client
            )
            mock_temp_client.__aexit__ = AsyncMock(side_effect=mock_aexit)
            mock_temp_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_temp_client

            with pytest.raises(json.JSONDecodeError):
                await create_mcp_from_openapi(
                    name="test",
                    openapi_url="https://api.example.com/invalid.json",
                )


class TestLoadMCPServersFromConfig:
    """Test load_mcp_servers_from_config function."""

    @pytest.mark.asyncio
    async def test_load_config_not_found(self, tmp_path):
        """Test loading when config file doesn't exist."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "nonexistent.json"
        result = await load_mcp_servers_from_config(str(config_path))

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_empty_config(self, tmp_path):
        """Test loading empty config (no servers)."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"servers": {}}))

        result = await load_mcp_servers_from_config(str(config_path))

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_single_server(self, tmp_path):
        """Test loading single server from config."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "petstore": {
                    "openapi_url": "https://petstore.example.com/openapi.json"
                }
            }
        }
        config_path.write_text(json.dumps(config))

        with patch(
            "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
        ) as mock_create:
            mock_server = MagicMock(name="petstore_server")
            mock_create.return_value = mock_server

            result = await load_mcp_servers_from_config(str(config_path))

            assert "petstore" in result
            assert result["petstore"] == mock_server
            mock_create.assert_called_once_with(
                name="petstore",
                openapi_url="https://petstore.example.com/openapi.json",
                auth_token=None,
                api_key=None,
                api_key_header="X-API-Key",
            )

    @pytest.mark.asyncio
    async def test_load_multiple_servers(self, tmp_path):
        """Test loading multiple servers from config."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "api1": {"openapi_url": "https://api1.com/openapi.json"},
                "api2": {"openapi_url": "https://api2.com/openapi.json"},
            }
        }
        config_path.write_text(json.dumps(config))

        with patch(
            "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
        ) as mock_create:
            mock_server1 = MagicMock(name="api1_server")
            mock_server2 = MagicMock(name="api2_server")
            mock_create.side_effect = [mock_server1, mock_server2]

            result = await load_mcp_servers_from_config(str(config_path))

            assert len(result) == 2
            assert "api1" in result
            assert "api2" in result
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_env_var_expansion(self, tmp_path):
        """Test environment variable expansion in config."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "github": {
                    "openapi_url": "https://api.github.com/openapi.json",
                    "auth_token": "${GITHUB_TOKEN}",
                }
            }
        }
        config_path.write_text(json.dumps(config))

        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token"}),
            patch(
                "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
            ) as mock_create,
        ):
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            result = await load_mcp_servers_from_config(str(config_path))

            assert "github" in result
            # Verify env var was expanded
            mock_create.assert_called_once()
            assert (
                mock_create.call_args.kwargs["auth_token"] == "ghp_test_token"
            )

    @pytest.mark.asyncio
    async def test_env_var_not_set(self, tmp_path):
        """Test handling of unset environment variables."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "api": {
                    "openapi_url": "https://api.example.com/openapi.json",
                    "auth_token": "${UNSET_VAR}",
                }
            }
        }
        config_path.write_text(json.dumps(config))

        with patch(
            "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
        ) as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            result = await load_mcp_servers_from_config(str(config_path))

            # Should still create server but with unexpanded variable
            assert "api" in result
            mock_create.assert_called_once()
            # Variable remains as ${UNSET_VAR}
            assert (
                mock_create.call_args.kwargs["auth_token"] == "${UNSET_VAR}"
            )

    @pytest.mark.asyncio
    async def test_server_creation_error(self, tmp_path):
        """Test handling when individual server creation fails."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "good": {
                    "openapi_url": "https://good.example.com/openapi.json"
                },
                "bad": {
                    "openapi_url": "https://bad.example.com/openapi.json"
                },
            }
        }
        config_path.write_text(json.dumps(config))

        with patch(
            "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
        ) as mock_create:
            mock_good = MagicMock(name="good_server")

            def side_effect(name, **kwargs):
                if name == "bad":
                    raise RuntimeError("Server creation failed")
                return mock_good

            mock_create.side_effect = side_effect

            result = await load_mcp_servers_from_config(str(config_path))

            # Should still return the successful server
            assert len(result) == 1
            assert "good" in result
            assert "bad" not in result

    @pytest.mark.asyncio
    async def test_config_with_api_key(self, tmp_path):
        """Test loading config with API key authentication."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config = {
            "servers": {
                "weatherapi": {
                    "openapi_url": "https://weatherapi.com/openapi.json",
                    "api_key": "abc123",
                    "api_key_header": "X-Weather-Key",
                }
            }
        }
        config_path.write_text(json.dumps(config))

        with patch(
            "bassi.core_v3.openapi_mcp.create_mcp_from_openapi"
        ) as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            result = await load_mcp_servers_from_config(str(config_path))

            assert "weatherapi" in result
            mock_create.assert_called_once_with(
                name="weatherapi",
                openapi_url="https://weatherapi.com/openapi.json",
                auth_token=None,
                api_key="abc123",
                api_key_header="X-Weather-Key",
            )

    @pytest.mark.asyncio
    async def test_invalid_json_config(self, tmp_path):
        """Test handling of invalid JSON in config file."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config_path.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            await load_mcp_servers_from_config(str(config_path))

    @pytest.mark.asyncio
    async def test_config_missing_servers_key(self, tmp_path):
        """Test config file without 'servers' key."""
        from bassi.core_v3.openapi_mcp import load_mcp_servers_from_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"other_key": "value"}))

        result = await load_mcp_servers_from_config(str(config_path))

        # Should return empty dict
        assert result == {}
