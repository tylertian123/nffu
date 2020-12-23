import asyncio
import datetime
import pymongo
from . import db # pylint: disable=unused-import # For type hinting
from .documents import TaskType


class TaskError(Exception):
    """
    Raised by task functions to indicate that an error has occurred.

    Tasks can optionally return a number of seconds to wait before retrying.
    This allows for the scheduler to keep track of retries.
    """

    def __init__(self, message, retry_in: float = None):
        super().__init__(message)
        self.retry_in = retry_in


class Scheduler:
    """
    Task scheduler.
    """

    # Actual coroutines to execute for tasks (dict of {task_type: coro})
    # Each coroutine should have signature (owner: User, retries: int) -> datetime.datetime
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
    
    async def _init(self):
        """
        Initialize the scheduler.

        Currently reports task that were interrupted, and set all tasks' is_running to false.
        """
        async for task in self._db.TaskImpl.find({"is_running": True}):
            print(f"Warning: Interrupted task: {task.kind} originally started on {task.next_run_at}.")
            task.is_running = False
            await task.commit()
    
    async def _run_task(self, task):
        """
        Run a specific task (given as a mongo Document).
        """
        if task.owner is not None:
            owner = await task.owner.fetch()
        else:
            owner = None
        # Run task
        try:
            next_run = await self.TASK_FUNCS[TaskType(task.kind)](owner, task.retry_count)
            # Task success, reset retries
            task.retry_count = 0
        except TaskError as e:
            if e.retry_in is not None:
                # Set next retry time and increase retry count
                next_run = datetime.datetime.now() + datetime.timedelta(seconds=e.retry_in)
                task.retry_count += 1
            else:
                # If no retry time given, task is deleted
                next_run = None
        # Update task if next run time is provided
        if next_run is not None:
            task.next_run_at = next_run
            task.is_running = False
            await task.commit()
        else:
            await task.remove()
    
    async def _run(self):
        """
        Main scheduling loop.
        """
        try:
            while True:
                # Find earliest scheduled task
                task = await self._db.TaskImpl.find_one({"is_running": False}, sort=[("next_run_at", pymongo.ASCENDING)])
                if task is None:
                    timeout = None
                else:
                    timeout = max((task.next_run_at - datetime.datetime.now()).total_seconds(), 0)
                try:
                    await asyncio.wait_for(self._update_event.wait(), timeout)
                    continue
                except asyncio.TimeoutError:
                    # Mark as running since create_task() doesn't force context switch
                    task.is_running = True
                    await task.commit()
                    asyncio.create_task(self._run_task(task))
        except asyncio.CancelledError:
            pass
    
    async def start(self):
        """
        Start the task scheduler.

        The main scheduling loop is started as an asyncio task.

        This method should only ever be called ONCE on startup.
        Subsequent calls may spawn more scheduling loops, causing unintended side effects.
        """
        await self._init()
        asyncio.create_task(self._run())
