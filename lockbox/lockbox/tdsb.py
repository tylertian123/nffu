"""
Handles getting info from TDSB.
"""

import datetime
import tdsbconnects
import typing


async def get_async_courses(session: tdsbconnects.TDSBConnects = None, logged_in: bool = False,
                            username: str = None, password: str = None) -> typing.List[tdsbconnects.TimetableItem]:
    """
    Get a list of asynchronous courses for this user, as pytdsbconnects TimetableItems.

    If session is provided, it will be used for this operation.
    Otherwise, a new session will be created.

    If session is provided and logged_in is true, the login process will be skipped.
    Otherwise, username and password must be provided, as they're required for login.

    Note that if a session is provided, it will not be closed at the end of the operation.
    """
    provided = session is not None
    if not provided:
        session = tdsbconnects.TDSBConnects()
    try:
        if not provided or not logged_in:
            await session.login(username, password)
        # Actually get the courses
        info = await session.get_user_info()
        found = []
        for school in info.schools:
            # Because we can only get this info through timetables for a specific date,
            # we must first find dates for each of the days in the cycle
            # so we can grab timetables for those dates later

            # The number of days to grab at a time for checking
            CHECK_RANGE = 14
            CYCLE_LENGTH = 4
            day_offsets = {}
            today = datetime.datetime.today()
            # Check up to 100 days into the future
            for i in range(0, 100, CHECK_RANGE):
                days = await school.day_cycle_names(today + datetime.timedelta(days=i), today + datetime.timedelta(days=i + CHECK_RANGE))
                for offset, day in enumerate(days):
                    # School days have the format "D<N>" where N is the number
                    # Non-school days are just "D"
                    if len(day) == 2 and day not in day_offsets:
                        day_offsets[day] = offset + i
                        if len(day_offsets) == CYCLE_LENGTH:
                            break
                if len(day_offsets) == CYCLE_LENGTH:
                    break
            for offset in day_offsets.values():
                timetable = await school.timetable(today + datetime.timedelta(days=offset))
                for item in timetable:
                    # Get only async periods
                    # Async periods have period strs ending in "a"
                    if item.course_period.endswith("a"):
                        found.append(item)
    finally:
        if not provided:
            await session.close()
    return found
    
