"""
Classes for storing and performing db operations.
"""

import aiohttp
import asyncio
import base64
import bson
import datetime
import logging
import os
import secrets
import typing
from cryptography.fernet import Fernet, InvalidToken
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from tdsbconnects import TDSBConnects, TimetableItem
from umongo import ValidationError, DeleteError
from umongo.frameworks import MotorAsyncIOInstance
from . import documents
from . import ghoster
from . import scheduler
from . import tasks


logger = logging.getLogger("db")


class LockboxDBError(Exception):
    """
    Raised to indicate an error when performing a lockbox db operation.
    """

    OTHER = 0
    BAD_TOKEN = 1
    INVALID_FIELD = 2
    INTERNAL_ERROR = 3
    STATE_CONFLICT = 4
    RATE_LIMIT_EXCEEDED = 5

    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


class LockboxDB:
    """
    Holds databases for lockbox.
    """

    def __init__(self, host: str, port: int):
        # Set up fernet
        # Read from base64 encoded key
        if os.environ.get("LOCKBOX_CREDENTIAL_KEY"):
            key = os.environ.get("LOCKBOX_CREDENTIAL_KEY")
        # Read from key file
        elif os.environ.get("LOCKBOX_CREDENTIAL_KEY_FILE"):
            try:
                with open(os.environ.get("LOCKBOX_CREDENTIAL_KEY_FILE"), "rb") as f:
                    key = base64.b64encode(f.read())
            except IOError as e:
                raise ValueError("Cannot read password encryption key file") from e
        else:
            raise ValueError("Encryption key for passwords must be provided! Set LOCKBOX_CREDENTIAL_KEY or LOCKBOX_CREDENTIAL_KEY_FILE.")
        # Should raise ValueError if key is invalid
        self.fernet = Fernet(key)

        self.client = AsyncIOMotorClient(host, port)
        self._private_db = self.client["lockbox"]
        self._shared_db = self.client["shared"]
        self._private_instance = MotorAsyncIOInstance(self._private_db)
        self._shared_instance = MotorAsyncIOInstance(self._shared_db)
        self._shared_gridfs = AsyncIOMotorGridFSBucket(self._shared_db)

        self.LockboxFailureImpl = self._private_instance.register(documents.LockboxFailure)
        self.FillFormResultImpl = self._private_instance.register(documents.FillFormResult)
        self.UserImpl = self._private_instance.register(documents.User)
        self.FormGeometryEntryImpl = self._private_instance.register(documents.FormGeometryEntry)
        self.CachedFormGeometryImpl = self._private_instance.register(documents.CachedFormGeometry)
        self.TaskImpl = self._private_instance.register(documents.Task)

        self.FormFieldImpl = self._shared_instance.register(documents.FormField)
        self.FormImpl = self._shared_instance.register(documents.Form)
        self.CourseImpl = self._shared_instance.register(documents.Course)

        self._scheduler = scheduler.Scheduler(self)
        tasks.set_task_handlers(self._scheduler)
        # Current school day, set by the check day task
        # Used as a fallback & indicator of whether the day's been checked
        # None when the day has not been checked
        self.current_day = None

    async def init(self):
        """
        Initialize the databases and task scheduler.
        """
        await self.UserImpl.ensure_indexes()
        await self.CourseImpl.ensure_indexes()
        await self.CachedFormGeometryImpl.collection.drop()
        await self.CachedFormGeometryImpl.ensure_indexes()
        await self._scheduler.start()

        # Re-schedule the check day task if current day is not checked
        if self.current_day is None:
            check_task = await self.TaskImpl.find_one({"kind": documents.TaskType.CHECK_DAY.value})
            if check_task is None:
                # Create check task if it does not exist
                await self._scheduler.create_task(kind=documents.TaskType.CHECK_DAY)
            # Check if the task will run later today
            # If the check task is set to run on a different date then make it run now
            elif check_task.next_run_at.replace(tzinfo=datetime.timezone.utc).astimezone(tasks.LOCAL_TZ).date() > datetime.datetime.today().date():
                check_task.next_run_at = datetime.datetime.utcnow()
                await check_task.commit()
                self._scheduler.update()

    def private_db(self) -> AsyncIOMotorDatabase:
        """
        Get a reference to the private database.
        """
        return self._private_db

    def shared_db(self) -> AsyncIOMotorDatabase:
        """
        Get a reference to the shared database.
        """
        return self._shared_db

    def shared_gridfs(self) -> AsyncIOMotorGridFSBucket:
        """
        Get a reference to the shared GridFS bucket.
        """
        return self._shared_gridfs

    async def _get_geometry(self, url: str, geom, user, password: str, grab_screenshot: bool):
        """
        Fill in form geometry. Also starts a task for deletion.
        """
        def _inner():
            try:
                auth_required, form_geom, screenshot_data = ghoster.get_form_geometry(url, ghoster.GhosterCredentials(user.email, user.login, password))
                geom.auth_required = auth_required
                geom.geometry = [{"index": entry[0], "title": entry[1], "kind": str(entry[2].value)} for entry in form_geom]
                return screenshot_data
            except ghoster.GhosterAuthFailed as e:
                geom.error = str(e)
                geom.response_status = 403
            except ghoster.GhosterInvalidForm as e:
                geom.error = str(e)
                geom.response_status = 400
        logger.info(f"Getting form geometry for {url}")
        screenshot_data = await asyncio.get_event_loop().run_in_executor(None, _inner)
        if grab_screenshot and screenshot_data is not None:
            geom.screenshot_file_id = await self._shared_gridfs.upload_from_stream("form-thumb.png", screenshot_data)
        await geom.commit()
        logger.info(f"Done getting form geometry for {url}")
        async def _delete_geom():
            try:
                await asyncio.sleep(15 * 60) # 15 mins
                try:
                    await geom.remove()
                    logger.info(f"Form geometry deleted for {url}")
                except DeleteError:
                    pass
            except asyncio.TimeoutError:
                pass
        asyncio.create_task(_delete_geom())

    async def populate_user_courses(self, user, courses: typing.List[TimetableItem]) -> None:
        """
        Populate a user's courses, creating new Course documents if new courses are encountered.
        """
        user.courses = []
        # Populate courses collection
        for course in courses:
            db_course = await self.CourseImpl.find_one({"course_code": course.course_code})
            if db_course is None:
                db_course = self.CourseImpl(course_code=course.course_code, teacher_name=course.course_teacher_name)
                # Without this, known_slots for different courses will all point to the same instance of list
                db_course.known_slots = []
            else:
                # Make sure the teacher name is set
                if not db_course.teacher_name:
                    db_course.teacher_name = course.course_teacher_name
            # Fill in known slots
            slot_str = f"{course.course_cycle_day}-{course.course_period}"
            if slot_str not in db_course.known_slots:
                db_course.known_slots.append(slot_str)
            await db_course.commit()
            if db_course.pk not in user.courses:
                user.courses.append(db_course.pk)
        await user.commit()

    async def create_user(self) -> str:
        """
        Create a new user.

        Returns token on success.
        """
        token = secrets.token_hex(32)
        await self.UserImpl(token=token).commit()
        return token

    async def modify_user(self, token: str, login: str = None, password: str = None, # pylint: disable=unused-argument
                          active: bool = None, grade: int = None, first_name: str = None,
                          last_name: str = None, **kwargs) -> None:
        """
        Modify user data.

        Also verifies credentials if modifying login or password.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        try:
            if login is not None:
                user.login = login
            if password is not None:
                user.password = self.fernet.encrypt(password.encode("utf-8"))
            if active is not None:
                user.active = active
            if grade is not None:
                user.grade = grade
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            # Verify user credentials if username and password are both present
            # and at least one is being modified
            if user.login is not None and user.password is not None and (login is not None or password is not None):
                logger.info(f"Verifying credentials for login {user.login}")
                try:
                    async with TDSBConnects() as session:
                        await session.login(login, password)
                        info = await session.get_user_info()
                        user.email = info.email
                        # Try to get user grade, first name, and last name
                        try:
                            user.grade = int(info._data["SchoolCodeList"][0]["StudentInfo"]["CurrentGradeLevel"]) + 1
                        except (ValueError, KeyError, IndexError):
                            pass
                        try:
                            user.first_name = info._data["SchoolCodeList"][0]["StudentInfo"]["FirstName"]
                            user.last_name = info._data["SchoolCodeList"][0]["StudentInfo"]["LastName"]
                        except (ValidationError, KeyError, IndexError):
                            pass
                except aiohttp.ClientResponseError as e:
                    user.email = None
                    logger.info(f"TDSB login error for login {user.login}")
                    # Invalid credentials, clean up and raise
                    if e.code == 401:
                        raise LockboxDBError("Incorrect TDSB credentials", LockboxDBError.INVALID_FIELD) from e
                    raise LockboxDBError(f"HTTP error while logging into TDSB Connects: {str(e)}") from e
                # Now we know credentials are valid
                # Set user courses to None to mark as pending
                user.courses = None
                await user.commit()
                logger.info(f"Credentials good for login {user.login}")
                await self._scheduler.create_task(kind=documents.TaskType.POPULATE_COURSES, owner=user)
            else:
                await user.commit()
        except ValidationError as e:
            raise LockboxDBError(f"Invalid field: {e}", LockboxDBError.INVALID_FIELD) from e

    async def get_user(self, token: str) -> typing.Dict[str, typing.Any]:
        """
        Get user data as a formatted dict.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        return user.dump()

    async def delete_user(self, token: str) -> None:
        """
        Delete a user by token.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        await user.remove()

    async def delete_user_error(self, token: str, eid: str) -> None:
        """
        Delete an error by id for a user.
        """
        try:
            result = await self.UserImpl.collection.update_one({"token": token},
                {"$pull": {"errors": {"_id": bson.ObjectId(eid)}}})
        except bson.errors.InvalidId as e:
            raise LockboxDBError("Bad error id") from e
        if result.matched_count == 0:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        if result.modified_count == 0:
            raise LockboxDBError("Bad error id")

    async def update_user_courses(self, token: str) -> None:
        """
        Refresh the detected courses for a user.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        if user.login is None or user.password is None:
            raise LockboxDBError("Cannot update courses: Missing credentials", LockboxDBError.STATE_CONFLICT)
        # Make sure the password is valid
        try:
            self.fernet.decrypt(user.password).decode("utf-8")
        except InvalidToken as e:
            logger.critical(f"User {user.pk}'s password cannot be decrypted")
            raise LockboxDBError("Internal server error: Cannot decrypt password", LockboxDBError.INTERNAL_ERROR) from e
        # Force courses into pending
        user.courses = None
        await user.commit()
        await self._scheduler.create_task(kind=documents.TaskType.POPULATE_COURSES, owner=user)

    async def get_form_geometry(self, token: str, url: str, override_limit: bool, grab_screenshot: bool) -> dict:
        """
        Get the form geometry for a given form URL.
        """
        user = await self.UserImpl.find_one({"token": token})
        if user is None:
            raise LockboxDBError("Bad token", LockboxDBError.BAD_TOKEN)
        if user.login is None or user.password is None:
            raise LockboxDBError("Cannot sign into form: Missing credentials", LockboxDBError.STATE_CONFLICT)
        # Attempt to decrypt the password here
        try:
            password = self.fernet.decrypt(user.password).decode("utf-8")
        except InvalidToken as e:
            logger.critical(f"User {user.pk}'s password cannot be decrypted")
            raise LockboxDBError("Internal server error: Cannot decrypt password", LockboxDBError.INTERNAL_ERROR) from e
        geom = await self.CachedFormGeometryImpl.find_one({"url": url})
        # Check if screenshot requirement is satisfied
        if geom is not None and grab_screenshot:
            screenshot_valid = False
            # If screenshot ID exists, check the GridFS bucket to make sure it's actually valid
            # the screenshot data may have been deleted by fenetre
            if geom.screenshot_file_id is not None:
                async for _ in self._shared_gridfs.find({"_id": geom.screenshot_file_id}):
                    screenshot_valid = True
                    break
        else:
            screenshot_valid = True
        # If this form was never requested before,
        # or the screenshot requirement is not satisfied AND the operation is not already pending
        if geom is None or (not screenshot_valid and geom.geometry is not None):
            existing = await self.CachedFormGeometryImpl.count_documents({"requested_by": token, "geometry": None})
            # Admin limit: 5
            if (override_limit and existing >= 5) or existing:
                raise LockboxDBError("Max number of requests at a time exceeded", LockboxDBError.RATE_LIMIT_EXCEEDED)

            # If this is a re-run, clear the old result
            if geom is not None:
                await geom.remove()

            try:
                geom = self.CachedFormGeometryImpl(url=url, requested_by=token, geometry=None)
            except ValidationError as e:
                raise LockboxDBError(f"Invalid field: {e}", LockboxDBError.INVALID_FIELD) from e
            await geom.commit()
            asyncio.create_task(self._get_geometry(url, geom, user, password, grab_screenshot))
            return {"geometry": None, "auth_required": None, "screenshot_id": None}
        # Result pending
        if geom.geometry is None and geom.response_status is None:
            return {"geometry": None, "auth_required": None, "screenshot_id": None}
        # Result exists
        if geom.response_status is None:
            return {"geometry": [e.dump() for e in geom.geometry], "auth_required": geom.auth_required, "screenshot_id": str(geom.screenshot_file_id)}
        return {
            "geometry": [e.dump() for e in geom.geometry],
            "screenshot_id": str(geom.screenshot_file_id),
            "auth_required": geom.auth_required,
            "error": geom.error,
            "status": geom.response_status
        }

    async def get_tasks(self) -> typing.List[dict]:
        """
        Get a list of serialized tasks.
        """
        return [task.dump() async for task in self.TaskImpl.find()]
