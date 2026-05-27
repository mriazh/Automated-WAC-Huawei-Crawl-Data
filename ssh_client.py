"""SSH session manager for WAC Huawei LLDP Crawl Data tool.

Manages SSH connection to WAC, handles interactive shell,
sends commands, and detects prompts using regex patterns.
"""

import logging
import re
import sys
import time

import paramiko

from config import Config

logger = logging.getLogger(__name__)

# Prompt detection patterns
WAC_USER_PROMPT = r"<[\w\-]+>"  # <WAC-1-GMF>
WAC_SYSTEM_PROMPT = r"\[[\w\-]+\]"  # [WAC-1-GMF]
AP_PROMPT = r"<[\w\-\s]+>"  # <AP-H3-L1-IN11>
YN_PROMPT = r"\[Y/N\]"  # Interactive Y/N question


class SSHSession:
    """Manages SSH connection to WAC with interactive shell support."""

    def __init__(self, config: Config):
        """Initialize with config. Does not connect yet.

        Args:
            config: Config dataclass with SSH connection parameters.
        """
        self.config = config
        self.client: paramiko.SSHClient | None = None
        self.channel: paramiko.Channel | None = None

    def connect(self) -> None:
        """Establish SSH connection and invoke interactive shell.

        Auto-accepts host key using paramiko AutoAddPolicy.
        Raises SystemExit on connection failure or timeout.
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                timeout=self.config.ssh_timeout,
            )
            self.channel = self.client.invoke_shell()
            # Allow shell to initialize
            time.sleep(1)
            # Drain initial banner/prompt output
            if self.channel.recv_ready():
                self.channel.recv(65535)
        except paramiko.AuthenticationException as e:
            print(f"Error: SSH authentication failed - {e}")
            sys.exit(1)
        except paramiko.SSHException as e:
            print(f"Error: SSH connection failed - {e}")
            sys.exit(1)
        except OSError as e:
            print(f"Error: Unable to connect to {self.config.host}:{self.config.port} - {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: SSH connection failed - {e}")
            sys.exit(1)

    def enter_system_view(self) -> None:
        """Send 'system-view' command and wait for [WAC] prompt.

        Raises SystemExit if prompt not received within 10 seconds.
        """
        try:
            self.send_command(
                "system-view",
                timeout=10,
                expect_patterns=[WAC_SYSTEM_PROMPT],
            )
        except TimeoutError:
            print("Error: Failed to enter system-view - prompt not received within 10 seconds")
            sys.exit(1)

    def send_command(
        self,
        command: str,
        timeout: int = 15,
        expect_patterns: list[str] | None = None,
    ) -> str:
        """Send command and wait for expected prompt patterns.

        Args:
            command: Command string to send to the shell.
            timeout: Maximum seconds to wait for prompt.
            expect_patterns: List of regex patterns to wait for.
                Defaults to [WAC_USER_PROMPT, WAC_SYSTEM_PROMPT].

        Returns:
            Collected output between command and prompt.

        Raises:
            TimeoutError: If no pattern matched within timeout.
        """
        if expect_patterns is None:
            expect_patterns = [WAC_USER_PROMPT, WAC_SYSTEM_PROMPT]

        self.channel.send(command + "\n")
        return self.wait_for_prompt(patterns=expect_patterns, timeout=timeout)

    def wait_for_prompt(
        self,
        patterns: list[str],
        timeout: int = 30,
        auto_respond: dict[str, str] | None = None,
    ) -> str:
        """Wait for any regex pattern in shell output.

        Args:
            patterns: List of regex patterns to match against output.
            timeout: Maximum seconds to wait for a pattern match.
            auto_respond: Dict mapping pattern -> response to send
                automatically (used for Y/N prompts during stelnet).
                When a pattern matches, the response is sent and that
                portion of the buffer is consumed. The timer resets
                after each auto-response to allow for subsequent prompts.

        Returns:
            Full output buffer when a pattern matches.

        Raises:
            TimeoutError: If timeout exceeded without matching any pattern.
        """
        buffer = ""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.channel.recv_ready():
                chunk = self.channel.recv(65535).decode("utf-8", errors="replace")
                buffer += chunk

                # Check auto-respond patterns first
                if auto_respond:
                    responded = True
                    while responded:
                        responded = False
                        for pattern, response in auto_respond.items():
                            if re.search(pattern, buffer):
                                self.channel.send(response + "\n")
                                # Clear the matched portion from buffer
                                buffer = re.split(pattern, buffer, maxsplit=1)[-1]
                                # Reset timer after auto-response
                                start_time = time.time()
                                responded = True
                                break

                # Check expected prompt patterns
                for pattern in patterns:
                    if re.search(pattern, buffer):
                        return buffer
            else:
                time.sleep(0.1)

        raise TimeoutError(
            f"Timeout ({timeout}s) waiting for patterns: {patterns}"
        )

    def disconnect(self) -> None:
        """Close SSH channel and transport gracefully.

        Logs warning if already disconnected. Handles exceptions
        during cleanup to ensure best-effort resource release.
        """
        if self.channel is None and self.client is None:
            logger.warning("SSH connection already closed")
            return

        try:
            if self.channel is not None:
                self.channel.close()
        except Exception as e:
            logger.warning("Error closing SSH channel: %s", e)
        finally:
            self.channel = None

        try:
            if self.client is not None:
                transport = self.client.get_transport()
                if transport is not None and transport.is_active():
                    self.client.close()
                else:
                    logger.warning("SSH connection already closed")
        except Exception as e:
            logger.warning("Error closing SSH client: %s", e)
        finally:
            self.client = None
