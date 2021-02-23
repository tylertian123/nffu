"""
Task function definitions for the scheduler.
"""

import aiohttp
import asyncio
import bson
import datetime
import gridfs
import logging
import os
import random
import umongo
import tdsbconnects
import traceback
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
# Vars in local time, defaults are below
CHECK_DAY_RUN_TIME = (datetime.time(hour=4, minute=0), datetime.time(hour=4, minute=0))
FILL_FORM_RUN_TIME = (datetime.time(hour=7, minute=0), datetime.time(hour=9, minute=0))
FILL_FORM_RETRY_LIMIT = 3
FILL_FORM_RETRY_IN = 30 * 60 # half an hour
FILL_FORM_SUBMIT_ENABLED = True


if os.environ.get("LOCKBOX_CHECK_DAY_RUN_TIME"):
    tstart, tend = os.environ["LOCKBOX_CHECK_DAY_RUN_TIME"].split("-")
    tstart = datetime.datetime.strptime(tstart.strip(), "%H:%M:%S").time()
    tend = datetime.datetime.strptime(tend.strip(), "%H:%M:%S").time()
    CHECK_DAY_RUN_TIME = (tstart, tend)
if os.environ.get("LOCKBOX_FILL_FORM_RUN_TIME"):
    tstart, tend = os.environ["LOCKBOX_FILL_FORM_RUN_TIME"].split("-")
    tstart = datetime.datetime.strptime(tstart.strip(), "%H:%M:%S").time()
    tend = datetime.datetime.strptime(tend.strip(), "%H:%M:%S").time()
    FILL_FORM_RUN_TIME = (tstart, tend)
if os.environ.get("LOCKBOX_FILL_FORM_RETRY_LIMIT"):
    FILL_FORM_RETRY_LIMIT = int(os.environ["LOCKBOX_FILL_FORM_RETRY_LIMIT"])
if os.environ.get("LOCKBOX_FILL_FORM_RETRY_IN"):
    FILL_FORM_RETRY_IN = float(os.environ["LOCKBOX_FILL_FORM_RETRY_IN"])
if os.environ.get("LOCKBOX_FILL_FORM_SUBMIT_ENABLED"):
    FILL_FORM_SUBMIT_ENABLED = int(os.environ.get("LOCKBOX_FILL_FORM_SUBMIT_ENABLED")) == 1


class LockboxTaskFailure(Exception):
    """
    Internal exception for failures.

    Contains both a LockboxFailureType, a string message and a boolean of whether to retry.
    """

    def __init__(self, failure_type: LockboxFailureType, message: str, retry: bool = False):
        super().__init__()
        self.failure_type = failure_type
        self.message = message
        self.retry = retry


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


async def check_day(db: "db_.LockboxDB", owner, retries: int, argument: str) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
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
            # First find the right school
            schools = (await session.get_user_info()).schools
            if db.school_code is not None:
                for s in schools:
                    if s.code == db.school_code:
                        school = s
                        break
                else:
                    logger.warning(f"User {user.pk} is not in the correct school")
                    # Skip if not in the correct school
                    continue
            else:
                if len(schools) != 1:
                    logger.warning(f"User {user.pk} is in {len(schools)} schools")
                    continue
                school = schools[0]
            days = await school.day_cycle_names(datetime.datetime.today(), datetime.datetime.today())
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


async def _get_tdsb_user_info(db: "db_.LockboxDB", user, password: str, warn_cb: typing.Callable[[LockboxFailureType, str], typing.Awaitable], # pylint: disable=unused-argument
                              log_prefix: str = "Get user school") -> typing.Tuple[tdsbconnects.User, tdsbconnects.School, typing.List[tdsbconnects.TimetableItem]]:
    """
    Attempt to get user info, school, and async timetable items from TDSB Connects.

    warn_cb is an async callback used for reporting warnings.
    Raises a LockboxTaskFailure on failure.
    """
    # Ideal case: Use fresh data from TDSB Connects
    try:
        async with tdsbconnects.TDSBConnects() as session:
            await session.login(user.login, password)
            info = await session.get_user_info()
            if db.school_code is not None:
                for s in info.schools:
                    if s.code == db.school_code:
                        school = s
                        break
                else:
                    logger.error(f"{log_prefix}: User {user.pk} is not in the right school")
                    raise LockboxTaskFailure(LockboxFailureType.BAD_USER_INFO, f"You don't seem to be in the school nffu was set up for (#{db.school_code}).")
            else:
                schools = info.schools
                if len(schools) != 1:
                    logger.error(f"{log_prefix}: User {user.pk} has an invalid number of schools: {', '.join(f'{s.name} (#{s.code})' for s in schools)}")
                    raise LockboxTaskFailure(LockboxFailureType.BAD_USER_INFO, f"TDSB reported that you're in {len(schools)} schools. NFFU only works if you have exactly 1 school.")
                school = schools[0]
            # Get only async courses today
            timetable = [item for item in (await school.timetable(datetime.date.today()) or ())
                         if item.course_period.endswith("a")]
            return info, school, timetable
    except aiohttp.ClientError as e:
        raise LockboxTaskFailure(LockboxFailureType.TDSB_CONNECTS, "TDSB Connects failed") from e


async def _get_fieldexpr_context(db: "db_.LockboxDB", user, course, info: typing.Optional[tdsbconnects.User],
                                 tdsb_course: typing.Optional[tdsbconnects.TimetableItem],
                                 warn_cb: typing.Callable[[LockboxFailureType, str], typing.Awaitable],
                                 log_prefix: str = "Get fieldexpr context") -> typing.Dict[str, typing.Any]:
    """
    Attempt to get the fieldexpr context used for form filling for a particular user and course.

    Information is extracted from the provided user info. If none, db info will be used.

    warn_cb is an async callback used for reporting warnings.
    Raises a LockboxTaskFailure on failure.
    """
    # Ideal case: Use fresh data from TDSB Connects
    if info is not None:
        # User-overridden first and last name
        if user.first_name or user.last_name:
            first_name = user.first_name
            last_name = user.last_name
        else:
            # Figure out the first and last name
            try:
                first_name = info._data["SchoolCodeList"][0]["StudentInfo"]["FirstName"]
                last_name = info._data["SchoolCodeList"][0]["StudentInfo"]["LastName"]
                if not first_name or not last_name:
                    raise ValueError()
            except (ValueError, IndexError, KeyError):
                logger.warning(f"{log_prefix}: No stored names for user {user.pk} and TDSB Connects does not contain first/last name. Attempting to split the full name")
                try:
                    # Fallback: Get first and last name by splitting the full name
                    i = info.name.index(", ")
                    first_name = info.name[:i]
                    last_name = info.name[i + 2:]
                except ValueError:
                    logger.warning(f"{log_prefix}: Failed to split the full name for user {user.pk}, setting both first and last name to {info.name}")
                    # Fallback fallback: Set first and last name to just the full name if there's no comma
                    first_name = last_name = info.name
        return {
            "name": first_name + " " + last_name, # Note: Changed in 0.1.11: This used to be Last, First as returned by TDSB Connects
            "first_name": first_name,
            "last_name": last_name,
            "student_number": user.login,
            "email": info.email,
            "today": datetime.date.today(),
            "grade": user.grade if user.grade is not None else 0,
            "course_code": tdsb_course.course_code if tdsb_course is not None else course.course_code,
            "teacher_name": tdsb_course.course_teacher_name if tdsb_course is not None else course.teacher_name,
            "teacher_email": tdsb_course.course_teacher_email if tdsb_course is not None else "unknown@tdsb.on.ca",
            "day_cycle": tdsb_course.course_cycle_day if tdsb_course is not None else (db.current_day if db.current_day is not None else 1),
        }
    else:
        # Worst case: Use the email to figure this out
        if not user.first_name or not user.last_name:
            logger.warning(f"{log_prefix}: Name not stored for user {user.pk}, using email to find out")
            try:
                addr = user.email.split("@")[0]
                first_name, last_name = addr.split(".")
                # Trim off the number
                for i, c in enumerate(last_name):
                    if c.isdigit():
                        last_name = last_name[:i]
                        break
            # Worst worst case, just default to empty :/
            except IndexError:
                logger.warning(f"{log_prefix}: Cannot figure out name for user {user.pk}")
                first_name = ""
                last_name = ""
                await warn_cb(LockboxFailureType.BAD_USER_INFO, "Warning: unable to determine your name, defaulting to empty. Please set it in the override pane.")
        else:
            first_name = user.first_name
            last_name = user.last_name
        # Populate fieldexpr context
        return {
            "name": first_name + " " + last_name, # Changed in 0.1.11, see comment in the if block
            "first_name": first_name,
            "last_name": last_name,
            "student_number": user.login,
            "email": user.email,
            "today": datetime.date.today(),
            "grade": user.grade if user.grade is not None else 0,
            "course_code": course.course_code,
            "teacher_name": course.teacher_name,
            "teacher_email": "unknown@tdsb.on.ca", # Can't figure this out from the user info
            "day_cycle": db.current_day if db.current_day is not None else 1, # This should've been checked before
        }


async def _do_fill_form(db: "db_.LockboxDB", user, course, password: str, fe_context: typing.Dict[str, typing.Any],
                        dry_run: bool, test: bool, warn_cb: typing.Callable[[LockboxFailureType, str], typing.Awaitable],
                        log_prefix: str = "Do fill form") -> typing.Any: # Returns db.FillFormResultImpl or db.FillFormResultImplShared
    """
    Actually fill a form.

    If test is true, the shared impl will be used and the confirm screenshot will not be taken.
    warn_cb is an async callback used for reporting warnings.
    Raises a LockboxTaskFailure on failure.
    """
    ResultImpl = db.FillFormResultImplShared if test else db.FillFormResultImpl
    ghoster_credentials = ghoster.GhosterCredentials(user.email, user.login, password)
    # Format fields
    fields = []
    form = await course.form_config.fetch()
    for field in form.sub_fields:
        try:
            value = fieldexpr.interpret(field.target_value, fe_context)
        # eww
        except Exception as e: # pylint: disable=broad-except
            logger.error(f"{log_prefix}: Field value formatting error: {e}")
            raise LockboxTaskFailure(LockboxFailureType.INTERNAL, f"Fill form: Field value formatting error: {e}", True) from e
        title = field.expected_label_segment or ""
        kind = FormFieldType(field.kind)
        fields.append((field.index_on_page, title, kind, value))
    logger.info(f"{log_prefix}: Form filling started for course {course.course_code} for user {user.pk}")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: ghoster.fill_form(course.form_url,
            ghoster_credentials, fields, dry_run=dry_run))
    except ghoster.GhosterPossibleFail as e:
        message, screenshot = e.args # pylint: disable=unbalanced-tuple-unpacking
        logger.warning(f"{log_prefix}: Possible failure for user {user.pk}: {message}\n{traceback.format_exc()}")
        # Upload screenshot and report error
        screenshot_id = await db.shared_gridfs().upload_from_stream("confirmation.png", screenshot)
        await warn_cb(LockboxFailureType.FORM_FILLING, f"Possible form filling failure (Not retrying): {message}")
        return ResultImpl(result=FillFormResultType.POSSIBLE_FAILURE.value,
            time_logged=datetime.datetime.utcnow(), confirmation_screenshot_id=screenshot_id, course=course.pk)
    except ghoster.GhosterError as e:
        if isinstance(e, ghoster.GhosterAuthFailed):
            fail_type = "Failed to login"
        elif isinstance(e, ghoster.GhosterInvalidForm):
            fail_type = "Invalid form"
        else:
            fail_type = "Unknown failure"
        logger.error(f"{log_prefix}: {fail_type} for user {user.pk}: {e}\n{traceback.format_exc()}")
        raise LockboxTaskFailure(LockboxFailureType.FORM_FILLING, f"{fail_type}: {e}", True) from e
    # Finally... all is well
    # Upload form and confirmation screenshots
    fss, css = result
    fid = await db.shared_gridfs().upload_from_stream("form.png", fss)
    fill_result = ResultImpl(result=FillFormResultType.SUCCESS.value if FILL_FORM_SUBMIT_ENABLED else FillFormResultType.SUBMIT_DISABLED.value,
        course=course.pk, time_logged=datetime.datetime.utcnow(), form_screenshot_id=fid)
    fill_result.confirmation_screenshot_id = await db.shared_gridfs().upload_from_stream("confirmation.png", css) if not test else fid
    logger.info(f"{log_prefix}: Finished for user {user.pk}")
    return fill_result


async def fill_form(db: "db_.LockboxDB", owner, retries: int, argument: str) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
    """
    Fills in the form for a particular user.
    """
    logger.info(f"Fill form: Starting for user {owner.pk} (login: {owner.login})")
    # No need to bother with recording errors for these two cases
    # Assumption: Form filling tasks exist if and only if a user has complete credentials and enabled form filling
    if not owner.active:
        raise scheduler.TaskError(f"User {owner.pk} has form filling disabled.")
    if owner.login is None or owner.password is None:
        raise scheduler.TaskError(f"User {owner.pk}'s credentials are incomplete")

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
    
    async def set_last_result(result):
        """
        Set the last fill form result field of the user.

        Clears the old result and deletes any images.
        
        Does NOT commit the user document.
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
        owner.last_fill_form_result = result

    async def handle_error(kind: LockboxFailureType, message: str, retry: bool = False, course=None) -> datetime.datetime:
        """
        Does error handling and handles either retrying or giving up and rescheduling.
        """
        await set_last_result(db.FillFormResultImpl(result=FillFormResultType.FAILURE.value,
            time_logged=datetime.datetime.utcnow()))
        # Ideally this shouldn't be necessary, but just in case
        if isinstance(course, umongo.Document):
            logger.warning("'course' argument passed to handle_error() was a Document instead of an ObjectId!")
            course = course.pk
        if course is not None:
            owner.last_fill_form_result.course = course
        # Report the failure
        if not retry:
            await report_failure(kind, message + "; Will not retry.")
            return next_run_time(FILL_FORM_RUN_TIME)
        else:
            if retries < FILL_FORM_RETRY_LIMIT:
                await report_failure(kind, message + "; Will retry later.")
                raise scheduler.TaskError(message, FILL_FORM_RETRY_IN)
            else:
                await report_failure(kind, message + "; Retry limit reached.")
                return next_run_time(FILL_FORM_RUN_TIME)

    if not FILL_FORM_SUBMIT_ENABLED:
        logger.warning("Form submitting is disabled right now, so we're not going to submit this form. Check the env vars if this is unexpected.")

    try:
        # Make sure password can be decrypted
        try:
            password = db.fernet.decrypt(owner.password).decode("utf-8")
        except InvalidToken:
            # PANIC!
            logger.critical(f"Fill form: User {owner.pk}'s password cannot be decrypted")
            return await handle_error(LockboxFailureType.INTERNAL, "Internal error: Failed to decrypt password")

        # Try and get data from TDSB Connects
        try:
            info, _, timetable = await _get_tdsb_user_info(db, owner, password, report_failure, "Fill form")
            # We got all we need, now find the Course document to fill the form for and populate fieldexpr_context
            # If no school today just return and come back tomorrow
            # This shouldn't happen
            if not timetable:
                logger.warning(f"Fill form: No school or async courses for user {owner.pk}")
                return next_run_time(FILL_FORM_RUN_TIME)
            # We are assuming only one async course per day
            tdsb_course = timetable[0]
            if len(timetable) > 1:
                missed_courses = ", ".join(f"{course.course_code} in period {course.course_period}" for course in timetable[1:])
                logger.warning(f"User {owner.pk} seems to have multiple async courses today. Missed courses: {missed_courses}")
                await report_failure(LockboxFailureType.BAD_USER_INFO, f"Warning: Multiple async courses detected for today, but only one form will be filled. Missed courses: {missed_courses}")
            # Re-populate courses just in case
            await db.populate_user_courses(owner, timetable, clear_previous=False)
            # Try to get the course from the database
            db_course = await db.CourseImpl.find_one({"course_code": tdsb_course.course_code})
            if db_course is None:
                logger.error(f"Fill form: User {owner.pk} populate courses failed for {tdsb_course.course_code}")
                return await handle_error(LockboxFailureType.INTERNAL, f"Internal error: Failed to find course for {tdsb_course.course_code}", True)
        # If that fails...
        except LockboxTaskFailure as e:
            if e.failure_type != LockboxFailureType.TDSB_CONNECTS:
                logger.error(f"Fill form: User {owner.pk} error {e.failure_type}: {e.message}")
                return await handle_error(e.failure_type, e.message, e.retry)
            else:
                info, tdsb_course = None, None
                # If TDSB Connects failed, use data stored in the db instead
                logger.warning(f"Fill form: TDSB Connects failed for user {owner.pk}: {e}")
                await report_failure(LockboxFailureType.TDSB_CONNECTS, f"Warning: TDSB Connects failed with error '{e}'. Falling back to stored data.")
                if db.current_day is None:
                    logger.error("Fill form: Cannot fall back to stored data, don't know what day it is")
                    return await handle_error(LockboxFailureType.TDSB_CONNECTS, f"Error: TDSB Connects error: '{e}'. Cannot fall back to stored data (don't know what day it is).", True)
                # Should never happen
                if db.current_day <= 0:
                    logger.warning("Fill form: Stored data indicates no school today. This shouldn't happen.")
                    return next_run_time(FILL_FORM_RUN_TIME)
                if not owner.courses:
                    logger.info(f"Fill form: No courses configured for user {owner.pk}")
                    return next_run_time(FILL_FORM_RUN_TIME)
                # Find the course that runs today
                db_course = None
                for course_id in owner.courses:
                    # Iterate through all courses the user has
                    course = await db.CourseImpl.find_one({"_id": course_id})
                    if course is None:
                        logger.error(f"Fill form: Broken course reference detected: Course {course_id} for user {owner.pk}.")
                        continue
                    # Check if the course runs this period
                    # This always assumes first period in the morning, should be fine
                    if f"{db.current_day}-1a" in course.known_slots:
                        db_course = course
                        break
                else:
                    logger.info(f"Fill form: No school or async courses for user {owner.pk}")
                    return next_run_time(FILL_FORM_RUN_TIME)

        try:
            # Get fieldexpr context
            fe_context = await _get_fieldexpr_context(db, owner, db_course, info, tdsb_course, report_failure, "Fill form")
        except LockboxTaskFailure as e:
            logger.error(f"Fill form: User {owner.pk} error {e.failure_type}: {e.message}")
            return await handle_error(e.failure_type, e.message, e.retry, course=db_course)

        # All the code above sets db_course, the Course document to fill the form for, and fieldexpr_context
        # Check that the form exists & is set up
        if not db_course.has_attendance_form:
            logger.info(f"Fill form: No form for course {db_course.course_code}")
            return next_run_time(FILL_FORM_RUN_TIME)
        if db_course.form_url is None or db_course.form_config is None:
            logger.warning(f"Fill form: Course missing form config: {db_course.course_code}")
            return await handle_error(LockboxFailureType.CONFIG, f"Course missing form config: {db_course.course_code}")
        
        # Start filling the form
        try:
            result = await _do_fill_form(db, owner, db_course, password, fe_context, not FILL_FORM_SUBMIT_ENABLED, False, report_failure, "Fill form")
        except LockboxTaskFailure as e:
            logger.error(f"Fill form: Filling failed for user {owner.pk} error {e.failure_type}: {e.message}")
            return await handle_error(e.failure_type, e.message, e.retry)
        # Set the result and finish
        await set_last_result(result)
        await owner.commit()
        logger.info(f"Fill form: Finished for user {owner.pk}")
        return next_run_time(FILL_FORM_RUN_TIME)
    except scheduler.TaskError:
        raise
    # Catch-all to make sure this never fails
    except Exception as e: # pylint: disable=broad-except
        logger.critical(f"Fill form: Unexpected exception: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        message = f"Critical internal error: {type(e).__name__}: '{e}'; Please contact an admin"
        db_course = locals().get("db_course")
        return await handle_error(LockboxFailureType.INTERNAL, message, True, course=db_course.pk if db_course is not None else None)

async def populate_courses(db: "db_.LockboxDB", owner, retries: int, argument: str) -> typing.Optional[datetime.datetime]: # pylint: disable=unused-argument
    """
    Get courses from TDSB connects for a user and populate the DB.
    """
    if owner.login is None or owner.password is None:
        raise scheduler.TaskError("User credentials are incomplete")
    try:
        password = db.fernet.decrypt(owner.password).decode("utf-8")
    except InvalidToken as e:
        logger.critical(f"User {owner.pk}'s password cannot be decrypted")
        raise scheduler.TaskError("Cannot decrypt user password") from e
    # Force owner courses into pending
    # NOTE: This action used to be required *before* the task is run, so that in the event of a failure,
    # if the user tried to update before the retry attempt, the retry won't need to do any extra work
    # However to facilitate refreshing all users' courses (for quad changes) this was removed
    owner.courses = None
    await owner.commit()
    try:
        courses = await tdsb.get_async_periods(username=owner.login, password=password, include_all_slots=True)
    except aiohttp.ClientError as e:
        # TODO: Improve this error handling
        raise scheduler.TaskError(f"TDSB Connects error: {e}", retry_in=600 if retries < 12 else None)
    await db.populate_user_courses(owner, courses, clear_previous=True)


async def _test_fill_form_inner(db: "db_.LockboxDB", owner, context) -> bool:
    """
    Try to fill in a form with mostly correct data, and save the results.

    Returns true if form was (at least somewhat) filled, returns false otherwise.
    """

    async def report_failure(kind: LockboxFailureType, message: str):
        """
        Report a lockbox failure by adding a document to this tests's list of failures.

        This does commit the context document.
        """
        failure = db.LockboxFailureImplShared(_id=bson.ObjectId(), time_logged=datetime.datetime.utcnow(),
                                        kind=kind.value, message=message)
        # Make sure it's a new list instance
        if not context.errors:
            context.errors = []
        context.errors.append(failure)
        await context.commit()

    async def set_last_result_error(course: bson.ObjectId = None, error_kind: str = FillFormResultType.FAILURE.value):
        """
        Set the result of this test to error.
        """

        result = db.FillFormResultImplShared(result=error_kind,
                                       time_logged=datetime.datetime.utcnow())
        # Ideally this shouldn't be necessary, but just in case
        if isinstance(course, umongo.Document):
            logger.warning("'course' argument passed to set_last_result_error() was a Document instead of an ObjectId!")
            course = course.pk
        if course is not None:
            result.course = course
        context.fill_result = result
        await context.commit()

    db_course = await db.CourseImpl.find_one({"_id": context.course_config})
    if db_course is None:
        logger.error("Test fill form: Context has invalid course")
        message = "Internal error: Failed to find course by id in test setup."
        await set_last_result_error()
        await report_failure(LockboxFailureType.INTERNAL, message)
        return False

    # grab password
    try:
        password = db.fernet.decrypt(owner.password).decode("utf-8")
    except InvalidToken:
        # PANIC!
        logger.critical(f"Test fill form: User {owner.pk}'s password cannot be decrypted")
        await set_last_result_error()
        await report_failure(LockboxFailureType.INTERNAL, "Internal error: Failed to decrypt password")
        return False

    # construct fieldexpr config
    # try tdsbconnects
    try:
        # School and timetable are not needed
        info, _, _ = await _get_tdsb_user_info(db, owner, password, report_failure, "Test fill form")
    except LockboxTaskFailure as e:
        if e.failure_type == LockboxFailureType.TDSB_CONNECTS:
            # Use stored info
            info = None
            await report_failure(LockboxFailureType.TDSB_CONNECTS, f"Warning: TDSB Connects failed with error '{e}'. Falling back to stored data.")
        else:
            logger.error(f"Test fill form: Cannot get user info for user {owner.pk}: {e.failure_type}: {e.message}")
            await set_last_result_error()
            await report_failure(e.failure_type, e.message)
            return False

    # Check that the form exists & is set up
    if not db_course.has_attendance_form:
        logger.info(f"Test fill form: No form for course {db_course.course_code}")
        return False
    if db_course.form_url is None or db_course.form_config is None:
        logger.warning(f"Test fill form: Course missing form config: {db_course.course_code}")
        await set_last_result_error(course=db_course.pk)
        await report_failure(LockboxFailureType.CONFIG, f"Course missing form config: {db_course.course_code}. Will not retry.")
        return False

    fieldexpr_context = await _get_fieldexpr_context(db, owner, db_course, info, None, report_failure, "Test fill form")
    try:
        context.fill_result = await _do_fill_form(db, owner, db_course, password, fieldexpr_context, True, True,
            report_failure, "Test fill form")
    except LockboxTaskFailure as e:
        await set_last_result_error(course=db_course.pk)
        await report_failure(LockboxFailureType.INTERNAL,
            e.message + (" Would've retried later." if e.retry else " Will not retry."))
        return False
    await context.commit()
    logger.info(f"Test fill form: Finished for user {owner.pk}")

    return True

async def test_fill_form(db: "db_.LockboxDB", owner, retries: int, argument: str):
    """
    Test filling in a form for a user for a specific course.
    """

    # try to find a context
    context = await db.find_form_test_context(argument)

    if context is None:
        logger.error(f"Test fill form: unable to find context for {argument}")
        
        # allow this to retry for race conditions
        if retries > 2:
            return
        else:
            raise scheduler.TaskError("Missing context, waiting", retry_in=5)

    context.time_executed = datetime.datetime.utcnow()

    # try to fill in form
    try:
        await _test_fill_form_inner(db, owner, context)
    finally:
        context.is_finished = True
        context.in_progress = False
        await context.commit()

async def remove_old_test_result(db: "db_.LockboxDB", owner, retries: int, argument: str): # pylint: disable=unused-argument
    """
    Remove an old result

    TODO: use a partial or something to reuse this code for other 'delete' tasks
    """

    # try to find a context
    context = await db.find_form_test_context(argument)

    if context is None:
        logger.warning(f"Test fill form cleanup: unable to find context for {argument}")

        return

    # cleanup screenshots if present
    if context.fill_result is not None and context.fill_result.form_screenshot_id is not None:
        try:
            await db.shared_gridfs().delete(context.fill_result.form_screenshot_id)
        except gridfs.NoFile:
            logger.warning(f"Test fill form cleanup: Failed to delete previous result form screenshot for user {context.pk}: No file")

    await context.remove()
    logger.info(f"Test fill form cleanup: removed {argument}")

def set_task_handlers(sched: "scheduler.Scheduler"):
    """
    Set the task handlers entries for the scheduler.
    """
    sched.TASK_FUNCS[TaskType.CHECK_DAY] = check_day
    sched.TASK_FUNCS[TaskType.FILL_FORM] = fill_form
    sched.TASK_FUNCS[TaskType.POPULATE_COURSES] = populate_courses
    sched.TASK_FUNCS[TaskType.TEST_FILL_FORM] = test_fill_form
    sched.TASK_FUNCS[TaskType.REMOVE_OLD_TEST_RESULTS] = remove_old_test_result
