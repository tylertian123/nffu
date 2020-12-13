"""
handles webdriver stuff
"""

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException


from lockbox.documents import FormFieldType
import collections

# Helper strucuts
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


def _guess_input_type(browser: webdriver.Firefox, element: webdriver.firefox.webelement.FirefoxWebElement):
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

def _get_input_header(browser: webdriver.Firefox, element: webdriver.firefox.webelement.FirefoxWebElement):
    """
    Get the header text
    """

    header_element = element.find_element_by_class_name("freebirdFormviewerComponentsQuestionBaseTitle")
    return header_element.text


class GhosterAuthFailed(Exception):
    pass

class GhosterInvalidForm(Exception):
    pass

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
            except NoSuchElementException:
                raise GhosterAuthFailed("Invalid authentication challenge page")
            except TimeoutException:
                raise GhosterAuthFailed("Invalid authentication")

        try:
            # ensure page is completely loaded
            WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "freebirdFormviewerViewNavigationSubmitButton"))) # if this times out the page is too complex
        except TimeoutException:
            if "alreadyresponded" in browser.current_url:
                raise GhosterInvalidForm("Form not setup for multiple responses")
            elif "formrestricted" in browser.current_url:
                raise GhosterAuthFailed("Account not able to access form")
            else:
                raise GhosterInvalidForm("Form doesn't have a submit button; may be multi-page?")

        # get all components on the page
        sub_elems = browser.find_elements_by_css_selector(".freebirdFormviewerViewItemList .freebirdFormviewerViewNumberedItemContainer")

        fields = []

        for j, elem in enumerate(sub_elems):
            f_type = _guess_input_type(browser, elem)
            if f_type is not None:
                try:
                    fields.append((j, _get_input_header(browser, elem), f_type))
                except NoSuchElementException:
                    raise GhosterInvalidForm(f"Form field {j} missing header")

        shot = browser.find_element_by_tag_name("html").screenshot_as_png

        return needs_signin, fields, shot
