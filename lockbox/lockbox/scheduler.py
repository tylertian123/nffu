"""
Task scheduler.

The scheduler works by keeping track of tasks in a mongodb collection.
See documents.Task for the format of task documents.
The scheduler runs a main loop and spawns asyncio tasks as necessary.
"""

import asyncio
import datetime
import logging
import typing
import pymongo
import traceback
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


class TaskTypeGroup:
    """
    A group of similar tasks sharing 1 rate limiting counter.

    One task may be in multiple of these.
    """

    __slots__ = ("name", "limit", "count")

    GROUPS_MAP = {} # type: typing.Dict[TaskType, typing.List["TaskTypeGroup"]]

    def __init__(self, name: str, types: typing.Tuple[TaskType], limit: int):
        self.name = name
        self.limit = limit
        self.count = 0
        for ttype in types:
            try:
                self.GROUPS_MAP[ttype].append(self)
            except KeyError:
                self.GROUPS_MAP[ttype] = [self]
    
    @classmethod
    def get_groups(cls, kind: TaskType) -> typing.Iterable["TaskTypeGroup"]:
        return cls.GROUPS_MAP.get(kind, ())


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

        # Initialize groups
        TaskTypeGroup("firefox", (TaskType.FILL_FORM, TaskType.TEST_FILL_FORM, TaskType.GET_FORM_GEOMETRY), 3)
        TaskTypeGroup("tdsb_connects", (TaskType.FILL_FORM, TaskType.CHECK_DAY, TaskType.POPULATE_COURSES, TaskType.TEST_FILL_FORM), 7)
        TaskTypeGroup("global", tuple(iter(TaskType)), 10)

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
            next_run = await self.TASK_FUNCS[TaskType(task.kind)](self._db, owner, task.retry_count, task.argument)
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
        except Exception: # pylint: disable=broad-except
            logger.critical(f"Task {self._format_task(task)} threw an unhandled error. Removing it from the database.")
            await task.remove()
            # log stracktrace
            logger.error("Exception traceback:\n" + traceback.format_exc())
            return
        # Update rate limiting counters
        for group in TaskTypeGroup.get_groups(TaskType(task.kind)):
            if group.count > 0:
                group.count -= 1
            else:
                logger.error(f"Inconsistent rate limiting count detected for group {group.name} ({self._format_task(task)})")
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
                # Calculate the amount of time to wait until the next task should execute
                # If no next task exists, wait forever
                if task is None:
                    timeout = None
                else:
                    # Calculate time to wait from the scheduled time of the task
                    timeout = (task.next_run_at - datetime.datetime.utcnow()).total_seconds()
                    # Only if the task is late by more than 100ms
                    # Since we don't want warnings for tasks that were scheduled to run immediately
                    if -timeout > 0.1:
                        logger.warning(f"Late task: {self._format_task(task)} (late {-timeout}s).")
                    timeout = max(timeout, 0)
                try:
                    await asyncio.wait_for(self._update_event.wait(), timeout)
                    # If wait_for() did not time out, then the update event must be set so check again for a new task
                    self._update_event.clear()
                    continue
                except asyncio.TimeoutError:
                    # If wait_for() timed out then we've waited the right amount of time to schedule the task
                    # Check rate limiting counters first
                    for group in TaskTypeGroup.get_groups(TaskType(task.kind)):
                        if group.count >= group.limit:
                            task.next_run_at += datetime.timedelta(seconds=30)
                            logger.warning(f"Task {self._format_task(task)} pushed back 30s because the rate limit for group {group.name} was reached ({group.limit})")
                            await task.commit()
                            break
                    # If didn't break, then all groups' requirements were met
                    else:
                        # Increase rate limiting counters and mark as running here since create_task() doesn't force context switch
                        for group in TaskTypeGroup.get_groups(TaskType(task.kind)):
                            group.count += 1
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

    async def create_task(self, kind: TaskType, run_at: typing.Optional[datetime.datetime] = None,
                owner: typing.Optional[typing.Any] = None, argument: typing.Optional[str] = None) -> typing.Any:
        """
        Create a new task.

        If run_at is not specified or None, the task will be scheduled immediately.
        Note that run_at is in *UTC*.

        Returns the created task document.
        """
        run_at = run_at or datetime.datetime.utcnow()
        task = self._db.TaskImpl(kind=kind.value, next_run_at=run_at)
        if owner is not None:
            task.owner = owner
        if argument is not None:
            task.argument = argument
        await task.commit()
        self.update()
        return task
