import logging
from typing import List, Optional
from stayssh.ssh.manager import SSHManager
from stayssh.core.models import TmuxOutputDTO

logger = logging.getLogger(__name__)

class TmuxManager:
    """Wraps tmux commands on the host machine."""

    def __init__(self, ssh: SSHManager) -> None:
        self.ssh = ssh

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

    async def create_session(self, name: str) -> bool:
        """Creates a new detached tmux session."""
        result = await self.ssh.run_command(f"tmux new-session -d -s {name}")
        if result.exit_code != 0:
            logger.error(f"Failed to create tmux session '{name}': {result.stderr}")
            return False
        return True

    async def kill_session(self, name: str) -> bool:
        """Kills a tmux session."""
        result = await self.ssh.run_command(f"tmux kill-session -t {name}")
        if result.exit_code != 0:
            logger.error(f"Failed to kill tmux session '{name}': {result.stderr}")
            return False
        return True

    async def send_keys(self, name: str, cmd: str) -> bool:
        """Sends a command to a tmux session."""
        # Enter is added to execute the command
        result = await self.ssh.run_command(f'tmux send-keys -t {name} "{cmd}" C-m')
        if result.exit_code != 0:
            logger.error(f"Failed to send keys to session '{name}': {result.stderr}")
            return False
        return True

    async def capture_pane(self, name: str, start_line: Optional[int] = None) -> Optional[TmuxOutputDTO]:
        """Captures the output of a tmux pane."""
        cmd = f"tmux capture-pane -p -t {name}"
        if start_line is not None:
            # Note: capturing from a specific line is tricky in raw tmux.
            # We capture all and let the caller diff, or use -S to specify start.
            pass
            
        result = await self.ssh.run_command(cmd)
        if result.exit_code != 0:
            logger.error(f"Failed to capture pane for '{name}': {result.stderr}")
            return None
        
        lines = result.stdout.splitlines()
        return TmuxOutputDTO(
            session_name=name,
            content=result.stdout,
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
