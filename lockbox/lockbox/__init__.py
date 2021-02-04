"""
The lockbox package handles storing user credentials and form filling information,
and actually filling out the forms.

At least one of the following environment variables are REQUIRED to be set:
    - LOCKBOX_CREDENTIAL_KEY:
        A base 64 encoded 32-byte key for encrypting users' TDSB credentials;
        if set, overrides LOCKBOX_CREDENTIAL_KEY_FILE.
    - LOCKBOX_CREDENTIAL_KEY_FILE:
        Path to a file containing a 32-byte key in raw binary for encrypting
        users' TDSB credentials; not used if LOCKBOX_CREDENTIAL_KEY is set.

The following environment variables are RECOMMENDED to be set but not required:
    - LOCKBOX_SCHOOL:
        The school code of the school that all the users should be in. Since
        nffu is designed to only handle users from one school, setting this
        will allow lockbox to ensure that no user from another school gets in
        the system.

The following environment variables MAY be set to customize lockbox's behaviour:
    - LOCKBOX_CHECK_DAY_RUN_TIME:
        A string in the (Python datetime) format "%H:%M:%S-%H:%M:%S" for the
        time range (both ends inclusive) in which the Check Day task runs.
        Times are in the local timezone. A random time will be chosen from the
        range for each run of the task. E.g. "04:00:00-05:00:00" sets the task
        to run sometime between 4am and 5am each day. Defaults to 4am-4am.
    - LOCKBOX_FILL_FORM_RUN_TIME:
        The time range in which the Fill Form tasks are to be run each day.
        Same format as LOCKBOX_CHECK_DAY_RUN_TIME. Defaults to 7am-9am.
    - LOCKBOX_FILL_FORM_RETRY_LIMIT:
        Limit for the number of retries for each Fill Form task. Defaults to 3.
    - LOCKBOX_FILL_FORM_RETRY_IN:
        The number of seconds to wait before retrying for each Fill Form task.
        Defaults to 1800 (30 minutes). This is a float.
    - LOCKBOX_FILL_FORM_SUBMIT_ENABLED:
        If set to anything other than 1, form submission will be disabled
        globally. Lockbox will still fill in the forms and take a screenshot to
        be reported back, but the form will not actually be submitted. Defaults
        to true (submit is enabled).
    - LOCKBOX_UPDATE_COURSES_BATCH_SIZE:
        The batch size (number of update operations to run at once) for
        updating all users' courses (typically run during a quad switch). Since
        the number of users can be large, users are divided into batches of
        this size, which are then run in sequence with the specified interval
        (see LOCKBOX_UPDATE_COURSES_INTERVAL). Defaults to 3.
    - LOCKBOX_UPDATE_COURSES_INTERVAL:
        The interval in seconds (amount of time to wait between batches) for
        updating all users' courses (typically run during a quad switch). See
        above for details. Note that this is the interval between the *start*
        of two batches, not between the end of one batch and the start of the
        next. Defaults to 60.
"""


import logging
from .server import LockboxServer

def setup_loggers(level: int):
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(name)s: %(message)s")
    handler.setFormatter(formatter)

    for name in ["scheduler", "task", "server", "db"]:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

    # aiohttp access gets separate handler for different format since it already has enough info
    ah_handler = logging.StreamHandler()
    ah_handler.setLevel(level)
    ah_logger = logging.getLogger("aiohttp.access")
    ah_logger.setLevel(level)
    ah_logger.addHandler(ah_handler)

def main():
    print("-------- lockbox started --------")
    setup_loggers(logging.DEBUG)
    print("Initializing lockbox server")
    server = LockboxServer()
    print("Starting lockbox server")
    server.run()
