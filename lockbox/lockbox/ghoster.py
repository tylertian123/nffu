"""
handles webdriver stuff
"""

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from typing import List, Tuple

from .documents import FormFieldType
import collections
import datetime

# Helper structs
GhosterCredentials = collections.namedtuple("GhosterCredentials", "email tdsb_user tdsb_pass")

# Various helper functions for doing common tasks
def _create_browser():
    options = Options()
    options.binary = "/opt/firefox/firefox"
    options.headless = True

    return webdriver.Firefox(options=options, service_log_path="/dev/null")

def _do_google_auth_flow(browser: webdriver.Firefox, credentials: GhosterCredentials):
    """
    Handle the google->aw auth flow.
    
    Expects the browser to be at a google login page and completes the login sequence.
    """

    # wait for the google page to load
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "identifierNext")))
    #print("google login loaded")

    # put the email into the google form
    browser.find_element_by_id("identifierId").send_keys(credentials.email)

    # click "next" in google
    browser.find_element_by_id("identifierNext").click()
    #print("going to aw page")

    # wait for the form to go to the aw site
    WebDriverWait(browser, 15).until(EC.url_contains("aw.tdsb.on.ca"))

    # wait for it to load
    WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.ID, "TdsbLoginControl_Login")))
    #print("aw page loaded")

    # fill in AW
    browser.find_element_by_id("UserName").send_keys(credentials.tdsb_user)
    browser.find_element_by_id("Password").send_keys(credentials.tdsb_pass)

    # click login
    browser.find_element_by_id("TdsbLoginControl_Login").click()
    #print("clicking login in aw")


def _guess_input_type(browser: webdriver.Firefox, element: webdriver.firefox.webelement.FirefoxWebElement): # pylint: disable=unused-argument
    """
    Try to figure out what kind of input this is.

    Returns None for unknown/ignored elements, otherwise a member of FormFieldType
    """

    # If this isn't a question, bail immediately
    if not len(element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionBaseRoot")):
        return None

    # Check for text question
    roots = element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionTextRoot")
    if roots:
        text_root = roots[0]
        # Check for short answer
        if text_root.find_elements_by_class_name("quantumWizTextinputPaperinputInput"):
            return FormFieldType.TEXT
        elif text_root.find_elements_by_class_name("quantumWizTextinputPapertextareaInput"):
            return FormFieldType.LONG_TEXT
        else:
            return None # unknown text-subtype
    
    # Check for radio root
    roots = element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionRadioRoot")
    if roots:
        if roots[0].find_elements_by_class_name("freebirdFormviewerViewItemsRadiogroupRadioGroup"):
            return FormFieldType.MULTIPLE_CHOICE
        else:
            return None

    # Check for date input
    if element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionDateInputsContainer"):
        return FormFieldType.DATE

    # Check for textbook input
    if element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionCheckboxRoot"):
        return FormFieldType.CHECKBOX

    # Check for dropdowns
    if element.find_elements_by_class_name("freebirdFormviewerComponentsQuestionSelectRoot"):
        return FormFieldType.DROPDOWN

    # Otherwise explicitly return None
    return None

def _get_input_header(browser: webdriver.Firefox, element: webdriver.firefox.webelement.FirefoxWebElement): # pylint: disable=unused-argument
    """
    Get the header text
    """

    header_element = element.find_element_by_class_name("freebirdFormviewerComponentsQuestionBaseTitle")
    return header_element.text

class GhosterAuthFailed(Exception):
    pass

class GhosterInvalidForm(Exception):
    pass

class GhosterPossibleFail(Exception):
    """
    Raised when an error _might_ have occurred and re-trying the operation could be dangerous

    (e.g. timed out waiting for page change after pressing submit)

    This error's args will be:
        (error message, screenshot of failing page for manual review)
    """

def _fill_in_field(browser: webdriver.Firefox, element: webdriver.firefox.webelement.FirefoxWebElement, with_value, kind: FormFieldType):
    """
    Fill in a field
    """

    if kind in [FormFieldType.TEXT, FormFieldType.LONG_TEXT]:
        text_field = element.find_element_by_css_selector("input.quantumWizTextinputPaperinputInput" if kind == FormFieldType.TEXT else "textarea.quantumWizTextinputPapertextareaInput")

        if not isinstance(with_value, str):
            raise TypeError()

        text_field.send_keys(with_value)

    elif kind == FormFieldType.DATE:
        if not isinstance(with_value, datetime.date):
            raise TypeError()

        components = element.find_elements_by_css_selector("input.quantumWizTextinputPaperinputInput")

        month = [x for x in components if x.get_attribute("max") == '12'][0]
        day   = [x for x in components if x.get_attribute("max") == '31'][0]
        year  = [x for x in components if int(x.get_attribute("min")) >= 1000][0]

        month.send_keys(str(with_value.month))
        day.send_keys(str(with_value.day))
        year.send_keys(str(with_value.year))

    elif kind in [FormFieldType.MULTIPLE_CHOICE, FormFieldType.DROPDOWN, FormFieldType.CHECKBOX]:
        if not isinstance(with_value, int):
            raise TypeError()

        if kind == FormFieldType.MULTIPLE_CHOICE:
            options = element.find_elements_by_class_name("docssharedWizToggleLabeledLabelWrapper")
            options[with_value].click()

        elif kind == FormFieldType.CHECKBOX:
            options = element.find_elements_by_class_name("quantumWizTogglePapercheckboxInnerBox")
            options[with_value].click()

        elif kind == FormFieldType.DROPDOWN:
            opener = element.find_element_by_class_name("quantumWizMenuPaperselectDropDown")
            opener.click()

            popup = element.find_element_by_class_name("exportSelectPopup")
            WebDriverWait(browser, 4, poll_frequency=0.25).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.exportSelectPopup .quantumWizMenuPaperselectOption")))
            options = popup.find_elements_by_class_name("exportOption")
            options[with_value + 1].click()  # + 1 for the "Choose" label

    else:
        raise NotImplementedError()


def fill_form(form_url: str, credentials: GhosterCredentials, components: List[Tuple[int, str, FormFieldType, object]]):
    """
    Fill in a form. Expects the URL, credentials and a description of what to fill in.

    The components array is structured as [
        (index, title, kind, value)...
    ]

    Returns two screenshots on success, the first being a picture of the form filled in and the second being a picture of the success screen.
    """

    with _create_browser() as browser:
        # load form
        browser.get(form_url)

        if "accounts.google.com" in browser.current_url:
            try:
                _do_google_auth_flow(browser, credentials) # if this times out the auth failed
            except NoSuchElementException as e:
                raise GhosterAuthFailed("Invalid authentication challenge page") from e
            except TimeoutException as e:
                raise GhosterAuthFailed("Invalid authentication") from e

        try:
            # ensure page is completely loaded
            WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "freebirdFormviewerViewNavigationSubmitButton"))) # if this times out the page is too complex
        except TimeoutException as e:
            if "alreadyresponded" in browser.current_url:
                raise GhosterInvalidForm("Form already responded to") from e
            elif "formrestricted" in browser.current_url:
                raise GhosterAuthFailed("Form not accessible by account") from e
            else:
                raise GhosterInvalidForm("Form doesn't have a submit button; may be multi-page?") from e

        # get all elements on the page
        sub_elems = browser.find_elements_by_css_selector(".freebirdFormviewerViewItemList .freebirdFormviewerViewNumberedItemContainer")
        
        for (index, expected_title, kind, value) in components:
            if index >= len(sub_elems):
                raise GhosterInvalidForm("Requested component (" + expected_title + ") is out of range")

            if expected_title not in _get_input_header(browser, sub_elems[index]):
                raise GhosterInvalidForm("Requested component (" + expected_title + ") is not present at index (" + str(index) + ")")

            try:
                _fill_in_field(browser, sub_elems[index], value, kind)
            except NoSuchElementException as e:
                raise GhosterInvalidForm("Requested component (" + expected_title + ") is of the wrong type (missing element)") from e
            except TimeoutException as e:
                raise GhosterInvalidForm("Requested component (" + expected_title + ") failed to fill in (timed out waiting for select)") from e
            except IndexError as e:
                raise GhosterInvalidForm("Requested component (" + expected_title + ") failed to fill in (option out of range)") from e
            except TypeError as e:
                raise GhosterInvalidForm("Requested component (" + expected_title + ") failed to fill in (invalid expression result type)") from e
            except NotImplementedError as e:
                raise GhosterInvalidForm("Requested component (" + expected_title + ") failed to fill in (kind not implemented)") from e


        # record screenshot of filled in page
        shot_pre = browser.find_element_by_tag_name("html").screenshot_as_png

        # locate submit button
        submit_button = browser.find_element_by_class_name("freebirdFormviewerViewNavigationSubmitButton")
        submit_button.click()

        try:
            WebDriverWait(browser, 10).until(EC.url_contains("formResponse"))
        except TimeoutException as e:
            raise GhosterPossibleFail("Timed out waiting for response page", browser.find_element_by_tag_name("html").screenshot_as_png) from e
        
        shot_post = browser.find_element_by_tag_name("html").screenshot_as_png

        return shot_pre, shot_post


def get_form_geometry(form_url: str, credentials: GhosterCredentials):
    """
    Retrieve information about the form

    This is:
        - whether or not the form needs authentication
        - all fillable fields:
            - page index
            - title
            - type

    Returned as (
        is_authenticated,
        [
            (field.idx, field.title, field.kind) for field in fields
        ],
        screnshot_of_page
    )
    """

    # spin up a browser
    with _create_browser() as browser:
        # go to the form url
        browser.get(form_url)

        needs_signin = False

        # check if the form needed signing in
        if "accounts.google.com" in browser.current_url:
            needs_signin = True
            try:
                _do_google_auth_flow(browser, credentials) # if this times out the auth failed
            except NoSuchElementException as e:
                raise GhosterAuthFailed("Invalid authentication challenge page") from e
            except TimeoutException as e:
                raise GhosterAuthFailed("Invalid authentication") from e

        try:
            # ensure page is completely loaded
            WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "freebirdFormviewerViewNavigationSubmitButton"))) # if this times out the page is too complex
        except TimeoutException as e:
            if "alreadyresponded" in browser.current_url:
                raise GhosterInvalidForm("Form not setup for multiple responses") from e
            elif "formrestricted" in browser.current_url:
                raise GhosterAuthFailed("Account not able to access form") from e
            else:
                raise GhosterInvalidForm("Form doesn't have a submit button; may be multi-page?") from e

        # get all components on the page
        sub_elems = browser.find_elements_by_css_selector(".freebirdFormviewerViewItemList .freebirdFormviewerViewNumberedItemContainer")

        fields = []

        for j, elem in enumerate(sub_elems):
            f_type = _guess_input_type(browser, elem)
            if f_type is not None:
                try:
                    fields.append((j, _get_input_header(browser, elem), f_type))
                except NoSuchElementException as e:
                    raise GhosterInvalidForm(f"Form field {j} missing header") from e

        # try to redact email before grabbing screenshot.
        try:
            email_tag = browser.find_element_by_class_name("freebirdFormviewerViewHeaderEmailAddress")
            browser.execute_script("arguments[0].innerText = '<redacted>'", email_tag)
        except NoSuchElementException:
            pass

        shot = browser.find_element_by_tag_name("html").screenshot_as_png

        return needs_signin, fields, shot
