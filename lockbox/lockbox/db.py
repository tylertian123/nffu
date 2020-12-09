"""
Classes for storing and performing db operations.
"""

import aiohttp
import asyncio
import base64
import bson
import os
import secrets
import typing
from cryptography.fernet import Fernet
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from tdsbconnects import TDSBConnects
from umongo import ValidationError
from umongo.frameworks import MotorAsyncIOInstance
from .documents import User, LockboxFailure, FormField, Form, Course
from . import tdsb


class LockboxDBError(Exception):
    """
    Raised to indicate an error when performing a lockbox db operation.
    """

    OTHER = 0
    BAD_TOKEN = 1
    INVALID_FIELD = 2

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

        self.LockboxFailureImpl = self._private_instance.register(LockboxFailure)
        self.UserImpl = self._private_instance.register(User)

        self.FormFieldImpl = self._shared_instance.register(FormField)
        self.FormImpl = self._shared_instance.register(Form)
        self.CourseImpl = self._shared_instance.register(Course)
        
    async def init(self):
        """
        Initialize the databases.
        """
        await self.UserImpl.ensure_indexes()
        await self.CourseImpl.ensure_indexes()
    
    def private_db(self) -> AsyncIOMotorDatabase:
        return self._private_db
    
    def shared_db(self) -> AsyncIOMotorDatabase:
        return self._shared_db
    
    async def create_user(self) -> str:
        """
        Create a new user.

        Returns token on success.
        """
        token = secrets.token_hex(32)
        await self.UserImpl(token=token).commit()
        return token

    async def modify_user(self, token: str, login: str = None, password: str = None, # pylint: disable=unused-argument
                          active: bool = None, **kwargs) -> None:
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
            # Verify user credentials if username and password are both present
            # and at least one is being modified
            if user["login"] is not None and user["password"] is not None and (login is not None or password is not None):
                print("Verifying credentials")
                session = TDSBConnects()
                try:
                    await session.login(login, password)
                except aiohttp.ClientResponseError as e:
                    # Invalid credentials, clean up and raise
                    await session.close()
                    if e.code == 401:
                        raise LockboxDBError("Invalid TDSB credentials", LockboxDBError.INVALID_FIELD) from e
                    raise LockboxDBError(f"HTTP error while logging into TDSB Connects: {str(e)}") from e
                # Now we know credentials are valid
                # Set user courses to None to mark as pending
                user.courses = None
                # Commit before creating the async task to avoid problems
                await user.commit()
                async def get_courses():
                    async with session:
                        courses = await tdsb.get_async_courses(session, logged_in=True)
                    user.courses = []
                    # Populate courses collection
                    for course in courses:
                        db_course = await self.CourseImpl.find_one({"course_code": course.course_code})
                        if db_course is None:
                            db_course = self.CourseImpl(course_code=course.course_code)
                        # Without this, known_slots for different courses will all point to the same instance of list
                        db_course.known_slots = db_course.known_slots or []
                        # Fill in known slots
                        slot_str = f"{course.course_cycle_day}-{course.course_period}"
                        if slot_str not in db_course.known_slots:
                            db_course.known_slots.append(slot_str)
                        await db_course.commit()
                        if db_course.pk not in user.courses:
                            user.courses.append(db_course.pk)
                    await user.commit()
                asyncio.create_task(get_courses())
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
