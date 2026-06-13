import logging
from typing import List, Optional
from tmux_ssh_telegram.ssh.manager import SSHManager
from tmux_ssh_telegram.core.models import TmuxOutputDTO

logger = logging.getLogger(__name__)

class TmuxManager:
    """Wraps tmux commands on the host machine."""

    def __init__(self, ssh: SSHManager) -> None:
        self.ssh = ssh

    async def check_and_provision(self) -> bool:
        """Checks if tmux is installed and attempts to install it if missing."""
        result = await self.ssh.run_command("which tmux")
        if result.exit_code == 0:
            return True

        logger.warning("tmux not found on host. Attempting to provision...")
        
        # Try to identify package manager and install
        # This is a basic implementation; in a real world, we might want more robust detection
        install_commands = [
            "sudo apt-get update && sudo apt-get install -y tmux",
            "sudo yum install -y tmux",
            "sudo apk add tmux",
            "brew install tmux"
        ]
        
        for cmd in install_commands:
            logger.info(f"Trying to install tmux with: {cmd}")
            install_result = await self.ssh.run_command(cmd)
            if install_result.exit_code == 0:
                logger.info("tmux successfully installed.")
                return True
        
        logger.error("Failed to provision tmux on host.")
        return False

    async def list_sessions(self) -> List[str]:
        """Lists active tmux session names on the host."""
        # -F "#{session_name}" ensures we only get the names
        result = await self.ssh.run_command('tmux ls -F "#{session_name}"')
        if result.exit_code != 0:
            if "no server running" in result.stderr or "error connecting to server" in result.stderr:
                return []
            logger.error(f"Failed to list tmux sessions: {result.stderr}")
            return []
        
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    async def create_session(self, name: str) -> Tuple[bool, str]:
        """Creates a new detached tmux session. Returns (success, error_message)."""
        result = await self.ssh.run_command(f"tmux new-session -d -s {name}")
        if result.exit_code != 0:
            err = f"tmux error: {result.stderr or 'Unknown error'}"
            logger.error(f"Failed to create tmux session '{name}': {err}")
            return False, err
        return True, ""

    async def kill_session(self, name: str) -> Tuple[bool, str]:
        """Kills a tmux session. Returns (success, error_message)."""
        result = await self.ssh.run_command(f"tmux kill-session -t {name}")
        if result.exit_code != 0:
            err = f"tmux error: {result.stderr or 'Unknown error'}"
            logger.error(f"Failed to kill tmux session '{name}': {err}")
            return False, err
        return True, ""

    async def send_keys(self, name: str, cmd: str, enter: bool = True) -> Tuple[bool, str]:
        """Sends a command to a tmux session. Returns (success, error_message)."""
        suffix = " C-m" if enter else ""
        result = await self.ssh.run_command(f"tmux send-keys -t {name} \"{cmd}\"{suffix}")
        if result.exit_code != 0:
            err = f"tmux error: {result.stderr or 'Unknown error'}"
            logger.error(f"Failed to send keys to session '{name}': {err}")
            return False, err
        return True, ""

    async def send_raw_key(self, name: str, key: str) -> Tuple[bool, str]:
        """Sends a raw tmux key sequence. Returns (success, error_message)."""
        result = await self.ssh.run_command(f"tmux send-keys -t {name} {key}")
        if result.exit_code != 0:
            err = f"tmux error: {result.stderr or 'Unknown error'}"
            logger.error(f"Failed to send raw key '{key}' to session '{name}': {err}")
            return False, err
        return True, ""

    async def capture_pane(self, name: str, start_line: Optional[int] = None) -> Optional[TmuxOutputDTO]:
        """Captures the output of a tmux pane, including history."""
        # -S - captures from the start of history
        # -J joins wrapped lines (optional, but good for clean output)
        cmd = f"tmux capture-pane -p -S - -t {name}"
            
        result = await self.ssh.run_command(cmd)
        if result.exit_code != 0:
            logger.error(f"Failed to capture pane for '{name}': {result.stderr}")
            return None
        
        # We rstrip() to ignore trailing empty lines in the visible pane,
        # ensuring the line count reflects actual content.
        content = result.stdout.rstrip()
        lines = content.splitlines()
        
        return TmuxOutputDTO(
            session_name=name,
            content=content,
            line_count=len(lines)
        )

    async def get_history(self, name: str, lines: int = 100) -> Optional[str]:
        """Gets the last N lines of history from a session."""
        # -S -N means capture from N lines ago
        result = await self.ssh.run_command(f"tmux capture-pane -p -S -{lines} -t {name}")
        if result.exit_code != 0:
            logger.error(f"Failed to get history for '{name}': {result.stderr}")
            return None
        return result.stdout
