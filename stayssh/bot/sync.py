import logging
from stayssh.db.repositories import SessionRepository
from stayssh.ssh.tmux import TmuxManager
from stayssh.core.models import SessionStatus

logger = logging.getLogger(__name__)

class SyncService:
    """Synchronizes host tmux sessions with the database."""

    def __init__(self, session_repo: SessionRepository, tmux_manager: TmuxManager):
        self.session_repo = session_repo
        self.tmux_manager = tmux_manager

    async def sync_on_startup(self, admin_id: int) -> None:
        """
        Reconciles the state of tmux sessions on the host with the DB.
        - Existing host sessions not in DB are added.
        - Sessions in DB but not on host are marked as DETACHED/DEAD.
        """
        logger.info("Synchronizing tmux sessions with host...")
        
        # 1. Get all sessions from host
        host_session_names = await self.tmux_manager.list_sessions()
        
        # 2. Get all active sessions from DB
        db_sessions = await self.session_repo.get_active_sessions()
        db_session_names = {s.name for s in db_sessions}

        # 3. Handle host sessions not in DB (Discovery)
        for name in host_session_names:
            if name not in db_session_names:
                logger.info(f"Discovered new host session: {name}. Adding to DB.")
                await self.session_repo.create(
                    name=name,
                    creator_id=admin_id,
                    description="Discovered from host on startup"
                )

        # 4. Handle DB sessions not on host (Cleanup/Sync)
        for db_session in db_sessions:
            if db_session.name not in host_session_names:
                logger.warning(f"Session {db_session.name} found in DB but missing on host. Marking as DEAD.")
                await self.session_repo.update_status(db_session.id, SessionStatus.DEAD)

        logger.info("Synchronization complete.")
