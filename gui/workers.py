"""Background workers for GUI crawl execution and connection verification.

Provides QThread-based CrawlWorker for non-blocking crawl operations
and QRunnable-based ConnectVerifier for SSH connection testing.
"""

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, QThread, Signal

from config import Config
from crawler import CrawlResult, crawl_all_aps
from ssh_client import SSHConnectionError, SSHSession

logger = logging.getLogger(__name__)


class CrawlWorker(QThread):
    """Background worker for crawl execution.

    Runs crawl_all_aps in a separate thread, emitting progress signals
    back to the GUI thread for live updates.
    """

    # Signals
    ap_progress = Signal(str, str, int, int)  # ap_name, status, current, total
    crawl_finished = Signal(str)  # "completed" | "stopped" | "connection_lost"
    crawl_error = Signal(str)  # error description

    def __init__(
        self,
        session: SSHSession,
        ap_list: list,
        switch_dict: dict[str, str],
        config: Config,
        already_done: set[str],
    ):
        """Initialize CrawlWorker with crawl parameters.

        Args:
            session: Active SSH session to the WAC controller.
            ap_list: List of APEntry objects to crawl.
            switch_dict: Mapping of switch names to IP addresses.
            config: Config dataclass with timeout settings.
            already_done: Set of AP names already crawled (resume mode).
        """
        super().__init__()
        self._session = session
        self._ap_list = ap_list
        self._switch_dict = switch_dict
        self._config = config
        self._already_done = already_done
        self._stop_event = threading.Event()
        self._current_count = 0
        self._total = len([ap for ap in ap_list if ap.name not in already_done])

    def run(self) -> None:
        """Execute crawl_all_aps with progress callback and stop check."""
        try:
            crawl_all_aps(
                self._session,
                self._ap_list,
                self._switch_dict,
                self._config,
                self._already_done,
                progress_callback=self._on_result,
                stop_check=self._should_stop,
            )

            if self._should_stop():
                self.crawl_finished.emit("stopped")
            else:
                self.crawl_finished.emit("completed")
        except SSHConnectionError as e:
            logger.error("SSH connection lost during crawl: %s", e)
            self.crawl_finished.emit("connection_lost")
        except Exception as e:
            logger.error("Unhandled error in CrawlWorker: %s", e)
            self.crawl_error.emit(str(e))

    def request_stop(self) -> None:
        """Set thread-safe stop flag to request crawl termination."""
        self._stop_event.set()

    def _on_result(self, result: CrawlResult) -> None:
        """Progress callback invoked by crawl_all_aps for each AP result.

        Increments the internal counter and emits ap_progress signal.
        """
        self._current_count += 1
        self.ap_progress.emit(
            result.ap_name,
            result.status,
            self._current_count,
            self._total,
        )

    def _should_stop(self) -> bool:
        """Check if stop has been requested (called between AP iterations)."""
        return self._stop_event.is_set()


class ConnectVerifier(QRunnable):
    """Verifies SSH connection without blocking the GUI thread.

    Uses QRunnable for lightweight thread pool execution. Emits signals
    via an inner Signals class since QRunnable cannot have signals directly.
    """

    class Signals(QObject):
        """Signals for ConnectVerifier results."""

        connected = Signal(object)  # SSHSession on success
        failed = Signal(str)  # error message on failure

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        ssh_timeout: int = 15,
    ):
        """Initialize ConnectVerifier with connection parameters.

        Args:
            host: SSH host address.
            port: SSH port number.
            username: SSH username.
            password: SSH password.
            ssh_timeout: Connection timeout in seconds.
        """
        super().__init__()
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssh_timeout = ssh_timeout
        self.signals = self.Signals()

    def run(self) -> None:
        """Attempt SSH connect with smart error differentiation.

        Uses paramiko directly but catches errors at different stages:
        - Socket/transport level errors → host/port problem
        - Authentication errors → credential problem
        """
        import socket
        from datetime import datetime

        logger.info("")
        logger.info("=" * 50)
        logger.info("CONNECTION START — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 50)
        logger.info("")
        logger.info("  Host     : %s", self._host)
        logger.info("  Port     : %d", self._port)
        logger.info("  Username : %s", self._username)
        logger.info("  Timeout  : %ds", self._ssh_timeout)
        logger.info("")

        import paramiko

        try:
            # Step 1: TCP + SSH handshake (verifies host, port, and SSH service)
            logger.info("  Step 1   : SSH handshake (host + port + SSH service)...")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # connect() does: TCP connect → SSH banner exchange → key exchange → auth
            # If it fails before auth, it's a host/port/service problem
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                timeout=self._ssh_timeout,
                auth_timeout=self._ssh_timeout,
            )
            logger.info("  Step 1   : OK (SSH connected + authenticated)")

            # Step 2: Enter system-view (verifies it's a WAC device)
            logger.info("  Step 2   : Enter system-view...")
            config = Config(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                ssh_timeout=self._ssh_timeout,
            )
            session = SSHSession(config)
            session.client = client
            session.channel = client.invoke_shell()

            import time
            time.sleep(1)
            if session.channel.recv_ready():
                session.channel.recv(65535)

            session.enter_system_view()
            logger.info("  Step 2   : OK (system-view entered)")
            logger.info("")
            logger.info("  Result   : SUCCESS")
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            self.signals.connected.emit(session)

        except paramiko.AuthenticationException as e:
            # Auth failed = host+port are CORRECT, credentials are WRONG
            logger.info("  Step 1   : Host/port OK, auth failed")
            logger.error("  Result   : FAILED (credentials)")
            logger.error("  Error    : %s", e)
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            self.signals.failed.emit("auth_failed")

        except (socket.timeout, OSError) as e:
            # Socket-level error = host/port problem
            error_str = str(e).lower()
            logger.error("  Step 1   : FAILED (network/socket)")
            logger.error("  Error    : %s", e)
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            if "timed out" in error_str or "10060" in error_str:
                self.signals.failed.emit("host_port_timeout")
            elif "refused" in error_str or "10061" in error_str:
                self.signals.failed.emit("host_port_refused")
            else:
                self.signals.failed.emit(f"host_port_error:{e}")

        except paramiko.SSHException as e:
            # SSH protocol error (banner not received, key exchange failed, etc.)
            # This means port is open but it's NOT a proper SSH server
            logger.error("  Step 1   : FAILED (SSH protocol error)")
            logger.error("  Error    : %s", e)
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            self.signals.failed.emit("ssh_protocol_error")

        except SSHConnectionError as e:
            # system-view failed = connected but not a WAC device
            error_str = str(e)
            logger.error("  Step 2   : FAILED")
            logger.error("  Error    : %s", e)
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            self.signals.failed.emit(f"not_wac:{error_str}")

        except Exception as e:
            logger.error("  Result   : FAILED (unexpected)")
            logger.error("  Error    : %s", e)
            logger.info("")
            logger.info("=" * 50)
            logger.info("CONNECTION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("=" * 50)
            logger.info("")
            self.signals.failed.emit(f"unexpected:{e}")
