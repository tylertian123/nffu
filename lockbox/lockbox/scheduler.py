import asyncio
import datetime
from . import db
from .documents import TaskType


class Scheduler:
    """
    Task scheduler.
    """

    TASK_FUNCS = {}

    def __init__(self, db: "db.LockboxDB"): # pylint: disable=redefined-outer-name
        self._db = db
        self._update_event = asyncio.Event()
    
    def update(self):
        """
        Tell the scheduler that a new task has been created.

        This updates the next task to be run.
        """
        self._update_event.set()
    
    async def _run_task(self, task):
        if task.owner is not None:
            owner = await task.owner.fetch()
        else:
            owner = None
        next_run = await self.TASK_FUNCS[TaskType(task.kind)](owner)
        if next_run is not None:
            task.next_run_at = next_run
            task.is_running = False
            await task.commit()
        else:
            await task.remove()
    
    async def _run(self):
        try:
            while True:
                # TODO: Make sure this isn't already running
                task = await self._db.TaskImpl.find_one(sort="next_run_at")
                if task is None:
                    timeout = None
                else:
                    timeout = max((task.next_run_at - datetime.datetime.now()).total_seconds(), 0)
                try:
                    asyncio.wait_for(self._update_event.wait(), timeout)
                    continue
                except asyncio.TimeoutError:
                    task.is_running = True
                    await task.commit()
                    asyncio.create_task(self._run_task(task))
        except asyncio.CancelledError:
            pass
