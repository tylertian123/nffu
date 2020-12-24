"""
Task scheduler.

The scheduler works by keeping track of tasks in a mongodb collection.
See documents.Task for the format of task documents.
The scheduler runs a main loop and spawns asyncio tasks as necessary.
"""

import asyncio
import datetime
import logging
import pymongo
from . import db # pylint: disable=unused-import # For type hinting
from .documents import TaskType


logger = logging.getLogger("scheduler")


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
    # Each coroutine should have signature (db: LockboxDB, owner: User, retries: int) -> datetime.datetime
    # The returned datetime should be in UTC!
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
    
    def _format_task(self, task) -> str:
        """
        Formats a task document as a string.
        """
        s = f"{task.kind} scheduled for {task.next_run_at}"
        if task.retry_count:
            s += f" ({task.retry_count} retries)"
        return s
    
    async def _init(self):
        """
        Initialize the scheduler.

        Currently reports task that were interrupted, and set all tasks' is_running to false.
        """
        async for task in self._db.TaskImpl.find({"is_running": True}):
            logger.warning(f"Detected interrupted task: {self._format_task(task)}.")
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
        logger.info(f"Starting task {self._format_task(task)}")
        # Run task
        try:
            next_run = await self.TASK_FUNCS[TaskType(task.kind)](self._db, owner, task.retry_count)
            # Task success, reset retries
            task.retry_count = 0
        except TaskError as e:
            if e.retry_in is not None:
                logger.warning(f"Task {self._format_task(task)} failed, retrying in {e.retry_in}s: {e}")
                # Set next retry time and increase retry count
                next_run = datetime.datetime.utcnow() + datetime.timedelta(seconds=e.retry_in)
                task.retry_count += 1
            else:
                logger.warning(f"Task {self._format_task(task)} failed, not retrying: {e}")
                # If no retry time given, task is deleted
                next_run = None
        # Update task if next run time is provided
        if next_run is not None:
            task.next_run_at = next_run
            task.is_running = False
            await task.commit()
            self.update()
            logger.info(f"Task rescheduled: {self._format_task(task)}")
        else:
            logger.info(f"Task success (deleted): {self._format_task(task)}")
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
                    timeout = (task.next_run_at - datetime.datetime.utcnow()).total_seconds()
                    if timeout < 0:
                        logger.warning(f"Late task: {self._format_task(task)} (late {-timeout}s).")
                        timeout = 0
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
