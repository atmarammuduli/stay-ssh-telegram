import asyncio
import logging
from typing import Optional, Tuple
import asyncssh
from tmux_ssh_telegram.core.config import settings
from tmux_ssh_telegram.core.models import CommandResultDTO

logger = logging.getLogger(__name__)

class SSHManager:
    """Manages the lifecycle of an SSH connection to the host machine."""

    def __init__(self) -> None:
        self.host: str = ""
        self.port: int = 22
        self.username: str = ""
        self._parse_url()
        
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self._lock = asyncio.Lock()

    def _parse_url(self) -> None:
        """Parses HOST_SSH_URL (ssh://user@host:port)."""
        url = settings.HOST_SSH_URL
        if url.startswith("ssh://"):
            url = url[6:]
        
        if "@" in url:
            self.username, host_part = url.split("@")
        else:
            host_part = url
            
        if ":" in host_part:
            self.host, port_str = host_part.split(":")
            self.port = int(port_str)
        else:
            self.host = host_part

    async def connect(self) -> bool:
        """Establishes the SSH connection if not already connected."""
        async with self._lock:
            if self.connection:
                return True
            
            try:
                logger.info(f"Connecting to host {self.host}:{self.port} as {self.username}...")
                self.connection = await asyncssh.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    client_keys=[settings.SSH_KEY_PATH],
                    known_hosts=None  # For simplicity, we skip host key verification here
                )
                logger.info("SSH Connection established.")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to host: {e}")
                self.connection = None
                return False

    async def ensure_connected(self) -> bool:
        """Ensures a connection exists, attempting to reconnect if needed."""
        if self.connection:
            return True
        return await self.connect()

    async def run_command(self, cmd: str) -> CommandResultDTO:
        """Executes a command on the host and returns a DTO."""
        if not await self.ensure_connected():
            return CommandResultDTO(
                exit_code=-1,
                stdout="",
                stderr="SSH Connection failed",
                duration=0.0
            )

        start_time = asyncio.get_event_loop().time()
        try:
            assert self.connection is not None
            result = await self.connection.run(cmd)
            duration = asyncio.get_event_loop().time() - start_time
            
            return CommandResultDTO(
                exit_code=result.exit_status or 0,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                duration=duration
            )
        except Exception as e:
            logger.error(f"Error executing command '{cmd}': {e}")
            self.connection = None  # Reset connection on error
            return CommandResultDTO(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=0.0
            )

    async def close(self) -> None:
        """Closes the SSH connection."""
        async with self._lock:
            if self.connection:
                self.connection.close()
                await self.connection.wait_closed()
                self.connection = None
                logger.info("SSH Connection closed.")
