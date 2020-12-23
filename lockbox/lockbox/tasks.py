"""
Task function definitions for the scheduler.
"""

import aiohttp
import datetime
import tdsbconnects
from cryptography.fernet import InvalidToken
from . import db
from . import scheduler
from .documents import TaskType


CHECK_DAY_RUN_TIME = datetime.time(hour=4, minute=0)


async def check_day(db: db.LockboxDB, owner, retries: int):
    """
    Checks if the current day is a school day.
    If not, postpones the run time of all tasks with type FILL_FORM by 1 day.

    This task should run daily before any forms are filled.
    """
    # Next run may not be exactly 1 day from now because of retries and other delays
    next_run = datetime.datetime.combine(datetime.datetime.today() + datetime.timedelta(days=1),
                                         CHECK_DAY_RUN_TIME)
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
        except aiohttp.ClientResponseError as e:
            if e.code != 401:
                print(f"Warning: CHECK_DAY: Non-401 HTTP error when trying to login as {user.login}: {e}")
            continue
        finally:
            await session.close()
    # Cannot find valid set of credentials or TDSB Connects is down?
    if day is None:
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
    else:
        # No school today
        db.current_day = -1
        await db.UserImpl.update_many({"kind": TaskType.FILL_FORM.value},
            [{"$set": {"next_run_at": {"$add": ["$next_run_at", 24 * 60 * 60 * 1000]}}}])
    return next_run


async def fill_form(db: db.LockboxDB, owner, retries: int):
    """
    Fills in the form for a particular user.
    """
    print("Fill form stub")


def set_task_handlers(scheduler):
    """
    Set the task handlers entries for the scheduler.
    """
    scheduler.TASK_FUNCS[TaskType.CHECK_DAY] = check_day
    scheduler.TASK_FUNCS[TaskType.FILL_FORM] = fill_form
