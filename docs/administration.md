# Managing NFFU

This document is a brief guide to managing and administering an NFFU instance. For configuring
and deploying one, see the [deployment guide](./deployment.md).

## User management

All things related to users an authentication are available from the "Authentication Config"
section of the webui.

From the "Users" section you can:

- Change peoples' passwords (in case they forget them, for example)
- Delete accounts
- Promote/unpromote users to administrators

The "Signup Providers" section lets you add/remove programs that can generate
signup codes. On this page you can:

- Create a new provider:
  
  Enter the name, then press the plus. You will see the secret token for this provider
  only once.
- Delete/unauthorize providers
- Manually create a signup code as any of the providers.

We recommend creating at least one signup provider, called "Manual" (or similar) and using
it to manually give people signup codes.

If you are trying to integrate an application with the NFFU signup code system, you
can use this python function which generates a signup code from a secret and current time:

```python
import hashlib
import hmac
import random

def generate_signup_code(hmac_secret: bytes, unix_time: int) -> str:
    """
    generate a signup code
    :param unix_time: should be in UTC
    """

    unix_minutes = unix_time // 60

    data = unix_minutes.to_bytes(8, byteorder='big', signed=False)
    mac  = hmac.new(hmac_secret, data, 'sha256').digest()
    i    = mac[-1] % 16
    trun = int.from_bytes(mac[i:i+4], byteorder='big', signed=False) % 2**31
    hexa = trun % 16**6

    digested = hashlib.sha256(hmac_secret).hexdigest()
    identifiers = [
        digested[i:i+3] for i in range(0, len(digested), 16)
    ]

    return random.choice(identifiers) + format(hexa, "06x")
```

## Form/course management

The "Forms" section allows you to manage configured form "styles" and course configurations.

### Form styles

NFFU uses the term _form style_ to denote a specific set of fields and responses that
a form can have. Users see the names/thumbnails of these on their "view configuration"
page.

You can configure form styles from the "Forms" subsection.

#### Creating a new form

You can do this by pressing the "New" button. On the presented dialog, you _must_ enter
a name, and can optionally provide a URL with which to initialize the thumbnail, or (optionally)
the fields.

#### Editing forms

From the "Edit" page you can change the name / thumbnail of a form, as well as setup the fields.

Each field contains:

- an index; which is the position of the question on the page starting at zero. Text-only boxes
  _are_ included in this. When in doubt, we recommend using the auto-fill from geometry feature
  when creating the form style.
- the "label"; which is the question text as shown on the page. This is considered valid if the value
  seen while filling in the form _contains_ the value on the configuration page; i.e. "Student number" would
  match "Student number (tdsb student id#)"
- the field's type
- is the field "critical?"; i.e. should we cancel filling if we can't find or if we fail to fill in this field.
- and the value expression. See [field expressions](./fieldexpr.md) for more.

Make sure you press the "Save" button after modifying the fields.

#### Marking a form as "default"

Default forms will be tested against any forms the user provides in their setup wizard. You
can enable/disable a form as being default from the main "Forms" page. Multiple forms can be
marked default.

### Configuring courses

Any courses NFFU finds will be listed here. 

On each course's "Edit configuration" page, you can both:

- view what users have submitted as this course's configuration (under "Edit configuration")
- override that configuration
- lock/unlock the course's configuration to users (shown as "verified/unverified")

Once a course is configured, you can also test it on the "test" page ("Test configuration **here**")

On this page, you can press "Run new test" to start a test, which will use _your_ personal information
combined with the data from the course to fill in the form; but not submit (similar to the "LOCKBOX_FILL_FORM_SUBMIT_ENABLED=0" option).

Test results are removed after 6 hours, and are only visible to the administrator who ran them.

## Lockbox administration

From the "Attendance Setup" section, administrators have an additional "Lockbox Admin" subsection.

Here, you can do two things. You can:

- **force refresh _all_ user courses**: useful at the beginning of a quad.
- view debug information about scheduled tasks.
