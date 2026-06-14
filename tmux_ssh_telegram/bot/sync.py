import logging
from tmux_ssh_telegram.db.repositories import SessionRepository
from tmux_ssh_telegram.ssh.tmux import TmuxManager
from tmux_ssh_telegram.core.models import SessionStatus

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
        
        try:
            # 1. Get all sessions from host
            host_session_names = await self.tmux_manager.list_sessions()
        except ConnectionError as e:
            logger.error(f"Sync aborted: SSH/Tmux connectivity issue: {e}")
            return # Skip sync, don't mark anything DEAD

        # 2. Get all sessions from DB (regardless of status, to avoid unique constraint)
        all_db_sessions = await self.session_repo.get_all()
        db_session_names = {s.name: s for s in all_db_sessions}

        # 3. Handle host sessions not in DB (Discovery)
        for name in host_session_names:
            if name not in db_session_names:
                logger.info(f"Discovered new host session: {name}. Adding to DB.")
                await self.session_repo.create(
                    name=name,
                    creator_id=admin_id,
                    description="Discovered from host on startup"
                )
            else:
                # If it exists but is marked as DEAD/DELETED, revive it
                existing = db_session_names[name]
                if existing.status == SessionStatus.DEAD:
                    logger.info(f"Reviving existing session: {name}.")
                    await self.session_repo.update_status(existing.id, SessionStatus.ACTIVE)

        # 4. Handle DB sessions not on host (Cleanup/Sync)
        for name, db_session in db_session_names.items():
            if name not in host_session_names and db_session.status == SessionStatus.ACTIVE:
                logger.warning(f"Session {db_session.name} found in DB but missing on host. Marking as DEAD.")
                await self.session_repo.update_status(db_session.id, SessionStatus.DEAD)

        logger.info("Synchronization complete.")
