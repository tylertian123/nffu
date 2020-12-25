"""
Task function definitions for the scheduler.
"""

import aiohttp
import asyncio
import bson
import datetime
import gridfs
import logging
import random
import tdsbconnects
import typing
from cryptography.fernet import InvalidToken
from dateutil import tz
from . import db as db_ # pylint: disable=unused-import
from . import fieldexpr
from . import ghoster
from . import scheduler
from . import tdsb
from .documents import LockboxFailureType, TaskType, FormFieldType, FillFormResultType


logger = logging.getLogger("task")


LOCAL_TZ = tz.gettz()
# TODO: Read these from env vars
# In local time
CHECK_DAY_RUN_TIME = (datetime.time(hour=4, minute=0), datetime.time(hour=4, minute=0))
FILL_FORM_RUN_TIME = (datetime.time(hour=7, minute=0), datetime.time(hour=9, minute=0))
FILL_FORM_RETRY_LIMIT = 3
FILL_FORM_RETRY_IN = 30 * 60 # half an hour


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
    logger.info("Check day: Starting")
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
            logger.critical(f"User {user.pk}'s password cannot be decrypted")
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
    logger.info(f"Fill form: Starting for user {owner.pk} (login: {owner.login})")
    # No need to bother with recording errors for these two cases
    # Assumption: Form filling tasks exist if and only if a user has complete credentials and enabled form filling
    if not owner.active:
        raise scheduler.TaskError(f"User {owner.pk} has form filling disabled.")
    if owner.login is None or owner.password is None:
        raise scheduler.TaskError(f"User {owner.pk} credentials are incomplete")

    async def report_failure(kind: LockboxFailureType, message: str):
        """
        Report a lockbox failure by adding a document to the user's list of failures.

        This does commit the user document.
        """
        failure = db.LockboxFailureImpl(_id=bson.ObjectId(), time_logged=datetime.datetime.utcnow(),
                                        kind=kind.value, message=message)
        # Make sure it's a new list instance
        if not owner.errors:
            owner.errors = []
        owner.errors.append(failure)
        await owner.commit()
    
    async def clear_last_result():
        """
        Clear the last fill form result of this user.

        This deletes the previous result and its assets if applicable.

        Note that this does NOT commit the owner document.
        """
        if owner.last_fill_form_result is not None:
            if owner.last_fill_form_result.form_screenshot_id is not None:
                try:
                    await db.shared_gridfs().delete(owner.last_fill_form_result.form_screenshot_id)
                except gridfs.NoFile:
                    logger.warning(f"Fill form: Failed to delete previous result form screenshot for user {owner.pk}: No file")
            if owner.last_fill_form_result.confirmation_screenshot_id is not None:
                try:
                    await db.shared_gridfs().delete(owner.last_fill_form_result.confirmation_screenshot_id)
                except gridfs.NoFile:
                    logger.warning(f"Fill form: Failed to delete previous result conformation page screenshot for user {owner.pk}: No file")
        owner.last_fill_form_result = None
    
    async def set_last_result_error():
        """
        Set the last fill form result of this user to error.

        This also deletes the previous result and its assets if applicable.

        Note that this does NOT commit the owner document.
        """
        await clear_last_result()
        owner.last_fill_form_result = db.FillFormResultImpl(result=FillFormResultType.FAILURE.value, time_logged=datetime.datetime.utcnow())
    
    # Make sure password can be decrypted
    try:
        password = db.fernet.decrypt(owner.password).decode("utf-8")
    except InvalidToken:
        # PANIC!
        logger.critical(f"Fill form: User {owner.pk}'s password cannot be decrypted")
        await set_last_result_error()
        await report_failure(LockboxFailureType.INTERNAL, "Internal error: Failed to decrypt password")
        return next_run_time(FILL_FORM_RUN_TIME)
    # Ideal case: Use fresh data from TDSB Connects
    try:
        async with tdsbconnects.TDSBConnects() as session:
            await session.login(owner.login, password)
            info = await session.get_user_info()
            if not info.schools:
                logger.error(f"Fill form: User {owner.pk} has no schools")
                await set_last_result_error()
                await report_failure(LockboxFailureType.BAD_USER_INFO, "TDSB Connects did not return any schools")
                return next_run_time(FILL_FORM_RUN_TIME)
            school = info.schools[0]
            # Get only async courses today
            timetable = [item for item in (await school.timetable(datetime.datetime.today()) or None)
                         if item.course_period.endswith("a")]
            # We got all we need
    except aiohttp.ClientError as e:
        # TODO implement fallback
        logger.warning(f"Fill form: TDSB Connects failed for user {owner.pk}")
        return next_run_time(FILL_FORM_RUN_TIME)
    
    if not timetable:
        logger.info(f"Fill form: No school or async courses for user {owner.pk}")
        return next_run_time(FILL_FORM_RUN_TIME)
    # We are assuming only one async course per day
    course = timetable[0]
    if len(timetable) > 1:
        missed_courses = ", ".join(f"{course.course_code} in period {course.course_period}" for course in timetable[1:])
        logger.warning(f"User {owner.pk} seems to have multiple async courses today. Missed courses: {missed_courses}")
        await report_failure(LockboxFailureType.BAD_USER_INFO, f"Warning: Multiple async courses detected for today, but only one form will be filled. Missed courses: {missed_courses}")
    # Re-populate courses just in case
    await db.populate_user_courses(owner, timetable)
    # Try to get the course from the database
    db_course = await db.CourseImpl.find_one({"course_code": course.course_code})
    if db_course is None:
        logger.error(f"Fill form: User {owner.pk} populate courses failed for {course.course_code}")
        message = f"Internal error: Failed to find course for {course.course_code}."
        await set_last_result_error()
        if retries < FILL_FORM_RETRY_LIMIT:
            await report_failure(LockboxFailureType.INTERNAL, message + " Will retry later.")
            raise scheduler.TaskError(message, FILL_FORM_RETRY_IN)
        else:
            await report_failure(LockboxFailureType.INTERNAL, message + " Retry limit reached.")
            return next_run_time(FILL_FORM_RUN_TIME)
    # Check that the form exists & is set up
    if not db_course.has_attendance_form:
        logger.info(f"Fill form: No form for course {course.course_code}")
        return next_run_time(FILL_FORM_RUN_TIME)
    if db_course.form_url is None or db_course.form_config is None:
        logger.warning(f"Fill form: Course missing form config: {course.course_code}")
        await set_last_result_error()
        await report_failure(LockboxFailureType.CONFIG, f"Course missing form config: {course.course_code}. Will not retry.")
        return next_run_time(FILL_FORM_RUN_TIME)
    # Figure out the first and last name
    try:
        first_name = info._data["SchoolCodeList"][0]["StudentInfo"]["FirstName"]
        last_name = info._data["SchoolCodeList"][0]["StudentInfo"]["FirstName"]
    except (IndexError, KeyError):
        try:
            # Fallback: Get first and last name by splitting the full name
            i = info.name.index(", ")
            first_name = info.name[:i]
            last_name = info.name[i + 2:]
        except ValueError:
            # Fallback fallback: Set first and last name to just the full name if there's no comma
            first_name = last_name = info.name
    # Populate fieldexpr context
    fieldexpr_context = {
        "name": info.name,
        "first_name": first_name,
        "last_name": last_name,
        "student_number": owner.login,
        "email": info.email,
        "today": datetime.datetime.now(),
        "grade": owner.grade if owner.grade is not None else 0,
        "course_code": course.course_code,
        "teacher_name": course.course_teacher_name,
        "teacher_email": course.course_teacher_email,
        "day_cycle": course.course_cycle_day,
    }
    ghoster_credentials = ghoster.GhosterCredentials(info.email, owner.login, password)
    # Format fields
    fields = []
    form = await db_course.form_config.fetch()
    for field in form.sub_fields:
        try:
            value = fieldexpr.interpret(field.target_value, fieldexpr_context)
        # eww
        except Exception as e: # pylint: disable=broad-except
            logger.error(f"Fill form: Field value formatting error: {e}")
            message = f"Field value formatting error: {e}."
            await set_last_result_error()
            if retries < FILL_FORM_RETRY_LIMIT:
                await report_failure(LockboxFailureType.INTERNAL, message + " Will retry later.")
                raise scheduler.TaskError(message, FILL_FORM_RETRY_IN)
            else:
                await report_failure(LockboxFailureType.INTERNAL, message + " Retry limit reached.")
                return next_run_time(FILL_FORM_RUN_TIME)
        title = field.expected_label_segment or ""
        kind = FormFieldType(field.kind)
        fields.append((field.index_on_page, title, kind, value))
    logger.info(f"Fill form: Form filling started for course {course.course_code}")
    def _inner():
        try:
            return ghoster.fill_form(db_course.form_url, ghoster_credentials, fields)
        except ghoster.GhosterError as e:
            return e
    result = await asyncio.get_event_loop().run_in_executor(None, _inner)
    if isinstance(result, ghoster.GhosterError):
        if isinstance(result, ghoster.GhosterPossibleFail):
            message, screenshot = result.args
            logger.warning(f"Fill form: Possible failure for user {owner.pk}: {message}")
            # Upload screenshot
            screenshot_id = await db.shared_gridfs().upload_from_stream("confirmation.png", screenshot)
            await clear_last_result()
            owner.last_fill_form_result = db.FillFormResultImpl(result=FillFormResultType.POSSIBLE_FAILURE.value,
                time_logged=datetime.datetime.utcnow(), confirmation_screenshot_id=screenshot_id)
            await report_failure(LockboxFailureType.FORM_FILLING, f"Possible form filling failure (Not retrying): {message}")
            return next_run_time(FILL_FORM_RUN_TIME)
        if isinstance(result, ghoster.GhosterAuthFailed):
            fail_type = "Failed to login"
        elif isinstance(result, ghoster.GhosterInvalidForm):
            fail_type = "Invalid form"
        else:
            fail_type = "Unknown failure"
        logger.error(f"Fill form: {fail_type} for user {owner.pk}: {result}")
        await set_last_result_error()
        if retries < FILL_FORM_RETRY_LIMIT:
            await report_failure(LockboxFailureType.FORM_FILLING, f"{fail_type} (will retry later): {result}")
            raise scheduler.TaskError(f"{fail_type}: {result}", FILL_FORM_RETRY_IN)
        else:
            await report_failure(LockboxFailureType.FORM_FILLING, f"{fail_type} (retry limit reached): {result}")
            return next_run_time(FILL_FORM_RUN_TIME)
    # Finally... all is well
    # Upload form and confirmation screenshots
    fss, css = result
    fid = await db.shared_gridfs().upload_from_stream("form.png", fss)
    cid = await db.shared_gridfs().upload_from_stream("confirmation.png", css)
    await clear_last_result()
    owner.last_fill_form_result = db.FillFormResultImpl(result=FillFormResultType.SUCCESS.value,
        time_logged=datetime.datetime.utcnow(), form_screenshot_id=fid, confirmation_screenshot_id=cid)
    await owner.commit()
    logger.info(f"Fill form: Finished for user {owner.pk}")
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
        logger.critical(f"User {owner.pk}'s password cannot be decrypted")
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
