"""
Task function definitions for the scheduler.
"""

import aiohttp
import datetime
import logging
import random
import tdsbconnects
import typing
from cryptography.fernet import InvalidToken
from dateutil import tz
from . import db as db_ # pylint: disable=unused-import
from . import scheduler
from . import tdsb
from .documents import TaskType


logger = logging.getLogger("task")


LOCAL_TZ = tz.gettz()
# In local time
CHECK_DAY_RUN_TIME = (datetime.time(hour=4, minute=0), datetime.time(hour=4, minute=0))
FILL_FORM_RUN_TIME = (datetime.time(hour=7, minute=0), datetime.time(hour=9, minute=0))


def next_run_time(time_range: typing.Tuple[datetime.time, datetime.time]) -> datetime.datetime:
    """
    Get the next time a task should run (in UTC) based on a time range (in local time).

    Both ends of the range are inclusive.

    The returned datetime will be in tomorrow in the provided range, in UTC.
    """
    start, end = time_range
    time_diff = (end.hour * 3600 + start.minute * 60 + end.second) - (start.hour * 3600 + start.minute * 60 + start.second)
    offset = random.randint(0, time_diff)
    return (datetime.datetime.combine(datetime.datetime.today() + datetime.timedelta(days=1), start, tzinfo=LOCAL_TZ)
        + datetime.timedelta(seconds=offset)).astimezone(datetime.timezone.utc)


async def check_day(db: "db_.LockboxDB", owner, retries: int) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
    """
    Checks if the current day is a school day.
    If not, postpones the run time of all tasks with type FILL_FORM by 1 day.

    This task should run daily before any forms are filled.
    """
    logger.info("Starting check day")
    # Next run may not be exactly 1 day from now because of retries and other delays
    next_run = next_run_time(CHECK_DAY_RUN_TIME)
    day = None
    # Try to get a set of valid credentials
    async for user in db.UserImpl.find():
        # Only use complete credentials for active users
        if not user.active or user.login is None or user.password is None:
            continue
        try:
            password = db.fernet.decrypt(user.password).decode("utf-8")
        except InvalidToken:
            continue
        # Attempt login
        session = tdsbconnects.TDSBConnects()
        try:
            await session.login(user.login, password)
            # Attempt to grab day
            schools = (await session.get_user_info()).schools
            if not schools:
                continue
            days = await schools[0].day_cycle_names(datetime.datetime.today(), datetime.datetime.today())
            if not days:
                continue
            day = days[0]
            break
        except aiohttp.ClientError as e:
            if not (isinstance(e, aiohttp.ClientResponseError) and e.code == 401): # pylint: disable=no-member
                logger.warning(f"Check day: Non-auth error when trying to login as {user.login}: {e}")
            continue
        finally:
            await session.close()
    # Cannot find valid set of credentials or TDSB Connects is down?
    if day is None:
        logger.warning("Check day: No valid credentials or TDSB Connects down")
        db.current_day = None
        # Retry one more time
        if retries < 1:
            # Retry in an hour
            raise scheduler.TaskError("No valid credentials or TDSB Connects down", retry_in=60 * 60)
        else:
            return next_run
    # "D<N>" format
    # There is school
    if len(day) >= 2:
        db.current_day = int(day[1:])
        logger.info(f"Check day: Current school day is a Day {db.current_day}")
    else:
        logger.info("Check day: No school today.")
        # No school today
        db.current_day = -1
        # Update only fill form tasks that are scheduled to run today
        start = datetime.datetime.now(tz=LOCAL_TZ)
        end = start.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        start = start.astimezone(datetime.timezone.utc)
        end = end.astimezone(datetime.timezone.utc)
        result = await db.TaskImpl.collection.update_many({"kind": TaskType.FILL_FORM.value,
                "next_run_at": {"$gte": start, "$lt": end}},
            [{"$set": {"next_run_at": {"$add": ["$next_run_at", 24 * 60 * 60 * 1000]}}}])
        logger.info(f"Check day: {result.modified_count} tasks modified.")
    return next_run


async def fill_form(db: "db_.LockboxDB", owner, retries: int) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
    """
    Fills in the form for a particular user.
    """
    logger.info("Fill form stub")
    return next_run_time(FILL_FORM_RUN_TIME)


async def populate_courses(db: "db_.LockboxDB", owner, retries: int) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
    """
    Get courses from TDSB connects for a user and populate the DB.

    Important: owner.courses should be set to None BEFORE this task runs.
    If courses is not None, this task will exit immediately to prevent doing unnecessary work.
    Current behaviour if TDSB Connects fails is to simply retry in 10 minutes with a limit of 12 retries.
    If a new populate courses task is started and succeeds after the previous one fails,
    owner.courses will be non-None, so the retry will just exit without doing extra work.
    """
    if owner.courses is not None:
        return None
    if owner.login is None or owner.password is None:
        raise scheduler.TaskError("User credentials are incomplete")
    try:
        password = db.fernet.decrypt(owner.password).decode("utf-8")
    except InvalidToken as e:
        raise scheduler.TaskError("Cannot decrypt user password") from e
    try:
        courses = await tdsb.get_async_periods(username=owner.login, password=password, include_all_slots=True)
    except aiohttp.ClientError as e:
        # TODO: Improve this error handling
        raise scheduler.TaskError(f"TDSB Connects error: {e}", retry_in=600 if retries < 12 else None)
    await db.populate_user_courses(owner, courses)


def set_task_handlers(sched: "scheduler.Scheduler"):
    """
    Set the task handlers entries for the scheduler.
    """
    sched.TASK_FUNCS[TaskType.CHECK_DAY] = check_day
    sched.TASK_FUNCS[TaskType.FILL_FORM] = fill_form
    sched.TASK_FUNCS[TaskType.POPULATE_COURSES] = populate_courses
