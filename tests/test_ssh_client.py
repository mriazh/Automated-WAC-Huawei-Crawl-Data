"""Unit tests for ssh_client.py with mocked paramiko.

Tests cover:
- connect/disconnect flow (Requirements 4.1–4.3, 10.1–10.4)
- send_command and wait_for_prompt (Requirements 4.4, 4.5)
- Timeout handling and auto-respond for Y/N prompts
- enter_system_view success and failure paths
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from config import Config
from ssh_client import (
    SSHConnectionError,
    SSHSession,
    WAC_USER_PROMPT,
    WAC_SYSTEM_PROMPT,
    AP_PROMPT,
    YN_PROMPT,
)


@pytest.fixture
def config():
    """Create a test Config instance."""
    return Config(
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret",
        ssh_timeout=10,
        ap_connect_timeout=10,
        command_timeout=5,
    )


@pytest.fixture
def mock_paramiko():
    """Patch paramiko.SSHClient and return mock objects."""
    with patch("ssh_client.paramiko.SSHClient") as mock_ssh_class:
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_transport = MagicMock()

        mock_ssh_class.return_value = mock_client
        mock_client.invoke_shell.return_value = mock_channel
        mock_client.get_transport.return_value = mock_transport
        mock_transport.is_active.return_value = True
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"<WAC-1-GMF>"
        mock_channel.closed = False

        yield {
            "ssh_class": mock_ssh_class,
            "client": mock_client,
            "channel": mock_channel,
            "transport": mock_transport,
        }


# ─── Connect Tests (Requirements 4.1, 4.2, 4.3) ───


class TestConnect:
    """Tests for SSHSession.connect()."""

    def test_connect_success(self, config, mock_paramiko):
        """connect() establishes SSH connection and opens interactive shell."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["client"].set_missing_host_key_policy.assert_called_once()
        mock_paramiko["client"].connect.assert_called_once_with(
            hostname="192.168.1.1",
            port=22,
            username="admin",
            password="secret",
            timeout=10,
        )
        mock_paramiko["client"].invoke_shell.assert_called_once()
        assert session.client is mock_paramiko["client"]
        assert session.channel is mock_paramiko["channel"]

    def test_connect_authentication_failure(self, config, mock_paramiko):
        """connect() raises SSHConnectionError on authentication failure."""
        import paramiko

        mock_paramiko["client"].connect.side_effect = paramiko.AuthenticationException(
            "Invalid credentials"
        )
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            with pytest.raises(SSHConnectionError):
                session.connect()

    def test_connect_ssh_exception(self, config, mock_paramiko):
        """connect() raises SSHConnectionError on SSH exception."""
        import paramiko

        mock_paramiko["client"].connect.side_effect = paramiko.SSHException(
            "Connection refused"
        )
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            with pytest.raises(SSHConnectionError):
                session.connect()

    def test_connect_os_error(self, config, mock_paramiko):
        """connect() raises SSHConnectionError on OS error (unreachable host)."""
        mock_paramiko["client"].connect.side_effect = OSError("Network unreachable")
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            with pytest.raises(SSHConnectionError):
                session.connect()

    def test_connect_generic_exception(self, config, mock_paramiko):
        """connect() raises SSHConnectionError on unexpected exceptions."""
        mock_paramiko["client"].connect.side_effect = RuntimeError("Unexpected")
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            with pytest.raises(SSHConnectionError):
                session.connect()

    def test_connect_drains_initial_banner(self, config, mock_paramiko):
        """connect() drains initial banner output from shell."""
        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = b"Welcome to WAC\n<WAC-1-GMF>"
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # recv should be called to drain the banner
        mock_paramiko["channel"].recv.assert_called()


# ─── Disconnect Tests (Requirements 10.1, 10.2, 10.4) ───


class TestDisconnect:
    """Tests for SSHSession.disconnect()."""

    def test_disconnect_closes_channel_and_client(self, config, mock_paramiko):
        """disconnect() closes both channel and SSH client."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()
            session.disconnect()

        mock_paramiko["channel"].close.assert_called_once()
        mock_paramiko["client"].close.assert_called_once()
        assert session.channel is None
        assert session.client is None

    def test_disconnect_already_disconnected(self, config):
        """disconnect() logs warning when already disconnected."""
        session = SSHSession(config)
        session.client = None
        session.channel = None

        # Should not raise, just log warning
        session.disconnect()

    def test_disconnect_handles_channel_close_error(self, config, mock_paramiko):
        """disconnect() handles errors during channel close gracefully."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].close.side_effect = Exception("Channel error")
        session.disconnect()

        # Client should still be cleaned up
        assert session.channel is None
        assert session.client is None

    def test_disconnect_handles_client_close_error(self, config, mock_paramiko):
        """disconnect() handles errors during client close gracefully."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["client"].close.side_effect = Exception("Client error")
        session.disconnect()

        assert session.client is None

    def test_disconnect_inactive_transport(self, config, mock_paramiko):
        """disconnect() logs warning when transport is already inactive."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["transport"].is_active.return_value = False
        session.disconnect()

        # Should not call client.close() when transport is inactive
        mock_paramiko["client"].close.assert_not_called()
        assert session.client is None

    def test_disconnect_sends_quit_commands(self, config, mock_paramiko):
        """disconnect() sends quit commands to WAC before closing."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()
            session.disconnect()

        # Should have sent quit commands via channel.send
        quit_calls = [
            call for call in mock_paramiko["channel"].send.call_args_list
            if call[0][0] == "quit\n"
        ]
        assert len(quit_calls) == 2


# ─── send_command Tests (Requirements 4.4, 4.5) ───


class TestSendCommand:
    """Tests for SSHSession.send_command()."""

    def test_send_command_basic(self, config, mock_paramiko):
        """send_command() sends command and returns output."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # Simulate channel returning output with prompt
        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = (
            b"display version\nHuawei WAC\n<WAC-1-GMF>"
        )

        result = session.send_command("display version")

        mock_paramiko["channel"].send.assert_called_with("display version\n")
        assert "Huawei WAC" in result

    def test_send_command_uses_default_patterns(self, config, mock_paramiko):
        """send_command() uses WAC_USER_PROMPT and WAC_SYSTEM_PROMPT by default."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = b"output\n[WAC-1-GMF]"

        result = session.send_command("some-command")
        assert "[WAC-1-GMF]" in result

    def test_send_command_custom_patterns(self, config, mock_paramiko):
        """send_command() accepts custom expect_patterns."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = b"output\n<AP-H3-L1-IN11>"

        result = session.send_command(
            "display lldp neighbor brief",
            timeout=5,
            expect_patterns=[AP_PROMPT],
        )
        assert "<AP-H3-L1-IN11>" in result

    def test_send_command_timeout(self, config, mock_paramiko):
        """send_command() raises TimeoutError when no pattern matches."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # Simulate no matching output (recv_ready returns False)
        mock_paramiko["channel"].recv_ready.return_value = False

        with patch("ssh_client.time.time") as mock_time:
            # Simulate time passing beyond timeout
            mock_time.side_effect = [0, 0, 5, 10, 20]
            with pytest.raises(TimeoutError):
                session.send_command("bad-command", timeout=5)


# ─── wait_for_prompt Tests ───


class TestWaitForPrompt:
    """Tests for SSHSession.wait_for_prompt()."""

    def test_wait_for_prompt_immediate_match(self, config, mock_paramiko):
        """wait_for_prompt() returns immediately when pattern is in buffer."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = b"Hello\n<WAC-1-GMF>"

        result = session.wait_for_prompt(
            patterns=[WAC_USER_PROMPT], timeout=5
        )
        assert "<WAC-1-GMF>" in result

    def test_wait_for_prompt_auto_respond_yn(self, config, mock_paramiko):
        """wait_for_prompt() auto-responds to Y/N prompts."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # First recv returns Y/N prompt, second returns AP prompt
        recv_responses = [
            b"Are you sure? [Y/N]:",
            b"\n<AP-H3-L1-IN11>",
        ]
        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.side_effect = recv_responses

        result = session.wait_for_prompt(
            patterns=[AP_PROMPT],
            timeout=10,
            auto_respond={YN_PROMPT: "Y"},
        )

        # Should have sent "Y\n" in response to the Y/N prompt
        send_calls = mock_paramiko["channel"].send.call_args_list
        yn_responses = [c for c in send_calls if c[0][0] == "Y\n"]
        assert len(yn_responses) >= 1
        assert "<AP-H3-L1-IN11>" in result

    def test_wait_for_prompt_multiple_auto_responds(self, config, mock_paramiko):
        """wait_for_prompt() handles multiple Y/N prompts with different responses."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # Simulate two Y/N prompts followed by AP prompt
        recv_responses = [
            b"Continue? [Y/N]:",
            b"Save config? [Y/N]:",
            b"\n<AP-H3-L1-IN11>",
        ]
        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.side_effect = recv_responses

        result = session.wait_for_prompt(
            patterns=[AP_PROMPT],
            timeout=10,
            auto_respond={YN_PROMPT: "Y"},
        )

        # Should have auto-responded to both Y/N prompts
        send_calls = mock_paramiko["channel"].send.call_args_list
        yn_responses = [c for c in send_calls if c[0][0] == "Y\n"]
        assert len(yn_responses) >= 2

    def test_wait_for_prompt_timeout_raises(self, config, mock_paramiko):
        """wait_for_prompt() raises TimeoutError when timeout exceeded."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = False

        with patch("ssh_client.time.time") as mock_time:
            mock_time.side_effect = [0, 0, 5, 10, 20]
            with pytest.raises(TimeoutError, match="Timeout"):
                session.wait_for_prompt(
                    patterns=[WAC_USER_PROMPT], timeout=5
                )

    def test_wait_for_prompt_resets_timer_on_auto_respond(self, config, mock_paramiko):
        """wait_for_prompt() resets timer after auto-responding."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # Use real time but with very short timeout to verify reset behavior
        # First call returns Y/N prompt, second returns final prompt
        call_count = [0]

        def recv_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return b"Prompt [Y/N]:"
            return b"<WAC-1-GMF>"

        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.side_effect = recv_side_effect

        result = session.wait_for_prompt(
            patterns=[WAC_USER_PROMPT],
            timeout=5,
            auto_respond={YN_PROMPT: "Y"},
        )
        assert "<WAC-1-GMF>" in result


# ─── enter_system_view Tests (Requirements 4.4, 4.5) ───


class TestEnterSystemView:
    """Tests for SSHSession.enter_system_view()."""

    def test_enter_system_view_success(self, config, mock_paramiko):
        """enter_system_view() succeeds when system prompt is received."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = True
        mock_paramiko["channel"].recv.return_value = b"[WAC-1-GMF]"

        # Should not raise
        session.enter_system_view()

        # Verify system-view command was sent
        send_calls = mock_paramiko["channel"].send.call_args_list
        sv_calls = [c for c in send_calls if "system-view" in c[0][0]]
        assert len(sv_calls) == 1

    def test_enter_system_view_timeout_exits(self, config, mock_paramiko):
        """enter_system_view() raises SSHConnectionError when prompt not received within 10s."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        mock_paramiko["channel"].recv_ready.return_value = False

        with patch("ssh_client.time.time") as mock_time:
            mock_time.side_effect = [0, 0, 5, 11, 20]
            with pytest.raises(SSHConnectionError):
                session.enter_system_view()

    def test_enter_system_view_wrong_prompt(self, config, mock_paramiko):
        """enter_system_view() raises SSHConnectionError when wrong prompt is received (timeout)."""
        session = SSHSession(config)

        with patch("ssh_client.time.sleep"):
            session.connect()

        # Return user prompt instead of system prompt — won't match [WAC] pattern
        mock_paramiko["channel"].recv_ready.return_value = False

        with patch("ssh_client.time.time") as mock_time:
            mock_time.side_effect = [0, 0, 5, 11, 20]
            with pytest.raises(SSHConnectionError):
                session.enter_system_view()
