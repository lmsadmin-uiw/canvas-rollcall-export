#!/usr/bin/env python3
"""
Canvas Roll Call Attendance Export Script
==========================================

This script automates the extraction of attendance data from Canvas LMS via the
Roll Call Attendance tool. It generates a CSV report and emails it to designated
recipients.

WHY SELENIUM?
-------------
The Roll Call Attendance tool (by Instructure) does not provide a direct API for
generating attendance reports. The only way to request a report is through the
Roll Call web interface. This script uses Selenium to automate that browser-based
form submission.

PROCESS OVERVIEW
----------------
1. Create a temporary Canvas API token (expires in 1 hour for security)
2. Generate a sessionless launch URL for the Roll Call LTI tool
3. Use Selenium (headless Chrome) to navigate to Roll Call and submit the report form
4. Delete the temporary token (cleanup)
5. Roll Call emails the report CSV to the configured address(es)

SCHEDULING NOTES
----------------
This script is designed to run as a scheduled task (cron on Linux, Task Scheduler
on Windows). The date logic automatically adjusts:
  - Monday: Pulls the previous 7 days (captures weekend entries from faculty)
  - Tuesday-Sunday: Pulls only the previous day

REQUIREMENTS
------------
See README.md for full setup instructions. Key dependencies:
  - Python 3.7+
  - Google Chrome browser
  - ChromeDriver (matching your Chrome version)
  - Python packages: requests, selenium

Author: Jon Whitney - Office of Teaching, Learning & Technology
Institution: University of the Incarnate Word
Version: 2.0
Last Updated: December 2025
"""

import requests
import logging
import sys
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time

# =============================================================================
# CONFIGURATION
# =============================================================================
# Update these values for your institution before running the script.

# Canvas API Configuration
# ------------------------
# ADMIN_API_TOKEN: A static access token from a Canvas admin account.
#                  This account must have permission to create tokens and
#                  launch LTI tools at the account level. Or, wherever (sub-account value) the Roll Call tool is implemented.
#                  Generate at: [Your Canvas URL]/profile/settings -> "New Access Token"
#
# USER_ID: The Canvas user ID for the account that generated ADMIN_API_TOKEN. There's likely a centralized
#          account that's an super admin in Canvas, recommended to use that kind of account.
#          Find this in the URL when viewing the user's profile in Canvas:
#          e.g., https://yourschool.instructure.com/users/12345 -> USER_ID = "12345"
#
# BASE_URL: Your institution's Canvas API base URL.
#           Format: https://[your-canvas-domain]/api/v1

ADMIN_API_TOKEN = ""  # YOUR MASTER ACCESS TOKEN HERE
USER_ID = ""          # YOUR USER ID HERE
BASE_URL = "https://yourschool.instructure.com/api/v1"  # UPDATE TO YOUR CANVAS URL

# Account ID for LTI Launch
# -------------------------
# This is typically "1" for the root account for Roll Call, but check your Canvas instance. 
# You can find this in the URL when viewing the account: /accounts/[ACCOUNT_ID]
ACCOUNT_ID = "1"

# Email Configuration
# -------------------
# The email address(es) where the attendance report will be sent.
# Roll Call will email the report download link to this address.
REPORT_EMAIL = "centralized-canvas-admin@yourschool.edu"  # UPDATE TO YOUR EMAIL

# To send to multiple recipients, uncomment and modify the line below instead:
# REPORT_EMAIL = "admin1@yourschool.edu, admin2@yourschool.edu, registrar@yourschool.edu"

# Logging Configuration
# ---------------------
# Set to True to write logs to a file in addition to console output.
# Log file will be created in the same directory as this script.
ENABLE_FILE_LOGGING = False  # Set to True for scheduled task environments

# Log file path (only used if ENABLE_FILE_LOGGING is True)
# You can specify an absolute path like "/var/log/attendance_export.log"
LOG_FILE_PATH = "attendance_export.log"

# Selenium Configuration
# ----------------------
# Adjust these timeouts if you experience issues with slow network/server responses.
PAGE_LOAD_TIMEOUT = 30      # Seconds to wait for Roll Call page to load
FORM_SUBMIT_WAIT = 5        # Seconds to wait after form submission
ELEMENT_WAIT_TIMEOUT = 10   # Seconds to wait for form elements to appear


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging():
    """
    Configure logging to output to console and optionally to a file.
    
    Log Format: [TIMESTAMP] LEVEL - Message
    Example: [2024-12-15 08:00:00] INFO - Temporary token created successfully
    """
    log_format = "[%(asctime)s] %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create logger
    logger = logging.getLogger("AttendanceExport")
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers if script is run multiple times in same session
    if logger.handlers:
        logger.handlers.clear()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if ENABLE_FILE_LOGGING:
        try:
            file_handler = logging.FileHandler(LOG_FILE_PATH)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(file_handler)
            logger.info(f"File logging enabled: {LOG_FILE_PATH}")
        except IOError as e:
            logger.warning(f"Could not create log file: {e}. Continuing with console only.")
    
    return logger


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_date_range():
    """
    Calculate the start and end dates for the attendance report.
    
    Logic:
    - On Mondays: Pull the previous 7 days to capture any attendance
      entries made over the weekend by faculty.
    - Tuesday through Sunday: Pull only the previous day.
    
    Returns:
        tuple: (start_date, end_date) as strings in MM/DD/YYYY format
    
    Note: Roll Call has a 6-day maximum range limit. The Monday logic
    (7 days back to yesterday) works because it's requesting data FOR
    those dates, not a 7-day span in the form's validation sense.
    """
    today = datetime.now()
    
    # Monday is weekday 0
    if today.weekday() == 0:
        # Monday: go back 7 days to capture the full previous week
        start_date = (today - timedelta(days=7)).strftime("%m/%d/%Y")
    else:
        # Tuesday-Sunday: just get yesterday
        start_date = (today - timedelta(days=1)).strftime("%m/%d/%Y")
    
    # End date is always yesterday
    end_date = (today - timedelta(days=1)).strftime("%m/%d/%Y")
    
    return start_date, end_date


def create_temporary_token(logger):
    """
    Create a short-lived Canvas API token for secure Roll Call access.
    
    This token expires in 1 hour, minimizing security risk. Even if the
    script fails before cleanup, the token will auto-expire.
    
    Args:
        logger: Logger instance for output
    
    Returns:
        tuple: (token_string, token_id) if successful
    
    Raises:
        SystemExit: If token creation fails
    """
    logger.info("Creating temporary API token...")
    
    create_token_url = f"{BASE_URL}/users/{USER_ID}/tokens"
    
    payload = {
        "token": {
            "purpose": "Temporary Attendance Report Script",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
    }
    
    headers = {
        "Authorization": f"Bearer {ADMIN_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        response = requests.post(create_token_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            new_token = token_data.get("visible_token")
            token_id = token_data.get("id")
            
            if not new_token:
                logger.error("API returned success but no token was included in response.")
                sys.exit(1)
            
            logger.info("Temporary token created successfully (expires in 1 hour)")
            return new_token, token_id
        else:
            logger.error(f"Failed to create token. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while creating token: {e}")
        sys.exit(1)


def delete_temporary_token(token_id, logger):
    """
    Delete the temporary token after use (security cleanup).
    
    This is a best-effort cleanup. If deletion fails, the token will
    still auto-expire after 1 hour.
    
    Args:
        token_id: The Canvas ID of the token to delete
        logger: Logger instance for output
    """
    logger.info("Cleaning up temporary token...")
    
    delete_url = f"{BASE_URL}/users/{USER_ID}/tokens/{token_id}"
    headers = {"Authorization": f"Bearer {ADMIN_API_TOKEN}"}
    
    try:
        response = requests.delete(delete_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info("Temporary token deleted successfully")
        else:
            logger.warning(f"Could not delete token (will auto-expire in <1 hour). Status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error during token cleanup (will auto-expire): {e}")


def get_sessionless_launch_url(temp_token, logger):
    """
    Generate a sessionless launch URL for the Roll Call LTI tool.
    
    A sessionless launch URL allows access to an LTI tool without
    requiring an interactive Canvas login. This is essential for
    automated/scheduled execution.
    
    Args:
        temp_token: The temporary API token to use for authentication
        logger: Logger instance for output
    
    Returns:
        str: The sessionless launch URL
    
    Raises:
        SystemExit: If URL generation fails
    """
    logger.info("Generating Roll Call sessionless launch URL...")
    
    rollcall_tool_url = "https://rollcall.instructure.com/launch"
    api_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/external_tools/sessionless_launch?url={rollcall_tool_url}"
    
    headers = {
        "Authorization": f"Bearer {temp_token}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            response_json = response.json()
            sessionless_url = response_json.get("url")
            
            if not sessionless_url:
                logger.error("API returned success but no URL in response.")
                return None
            
            logger.info("Sessionless launch URL retrieved successfully")
            return sessionless_url
        else:
            logger.error(f"Failed to get sessionless URL. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while getting sessionless URL: {e}")
        return None


def configure_chrome_driver(logger):
    """
    Configure and return a headless Chrome WebDriver instance.
    
    Headless mode runs Chrome without a visible window, which is
    required for scheduled tasks and server environments.
    
    Args:
        logger: Logger instance for output
    
    Returns:
        WebDriver: Configured Chrome WebDriver instance
    
    Raises:
        SystemExit: If Chrome/ChromeDriver setup fails
    """
    logger.info("Initializing headless Chrome browser...")
    
    chrome_options = Options()
    
    # Run without visible browser window
    chrome_options.add_argument("--headless")
    
    # Required for headless mode on some systems
    chrome_options.add_argument("--disable-gpu")
    
    # Required when running as root (common in Docker/server environments)
    chrome_options.add_argument("--no-sandbox")
    
    # Helps with stability in containerized environments
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set a reasonable window size (some sites behave differently on small viewports)
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        logger.info("Chrome browser initialized successfully")
        return driver
        
    except WebDriverException as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {e}")
        logger.error("Ensure Chrome and ChromeDriver are installed and compatible.")
        logger.error("See README.md for setup instructions.")
        sys.exit(1)


def submit_attendance_report_form(driver, start_date, end_date, sessionless_url, logger):
    """
    Navigate to Roll Call and submit the attendance report request form.
    
    Args:
        driver: Selenium WebDriver instance
        start_date: Report start date (MM/DD/YYYY format)
        end_date: Report end date (MM/DD/YYYY format)
        sessionless_url: The authenticated launch URL for Roll Call
        logger: Logger instance for output
    
    Returns:
        bool: True if form submitted successfully, False otherwise
    """
    logger.info("Navigating to Roll Call attendance report page...")
    
    try:
        driver.get(sessionless_url)
        
        # Wait for the form to be present (better than arbitrary sleep)
        wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
        
        logger.info(f"Filling report form: {start_date} to {end_date}")
        
        # Wait for and fill the start date field
        start_field = wait.until(
            EC.presence_of_element_located((By.NAME, "report[start_date]"))
        )
        start_field.clear()
        start_field.send_keys(start_date)
        
        # Fill the end date field
        end_field = driver.find_element(By.NAME, "report[end_date]")
        end_field.clear()
        end_field.send_keys(end_date)
        
        # Fill the email field
        # -----------------------------------------------------------------
        # CONFIGURING REPORT RECIPIENTS:
        # The report download link will be sent to REPORT_EMAIL (defined above).
        # To send to multiple addresses, set REPORT_EMAIL to a comma-separated
        # string, e.g.: "admin@school.edu, registrar@school.edu"
        # -----------------------------------------------------------------
        email_field = driver.find_element(By.NAME, "report[email]")
        email_field.clear()
        email_field.send_keys(REPORT_EMAIL)
        
        # Brief pause to ensure form is fully populated before submission
        # (Roll Call has been observed to error on rapid submissions)
        time.sleep(2)
        
        # Submit the form
        submit_button = driver.find_element(By.NAME, "commit")
        submit_button.click()
        
        logger.info("Form submitted successfully")
        
        # Allow time for server to process before closing browser
        time.sleep(FORM_SUBMIT_WAIT)
        
        return True
        
    except TimeoutException:
        logger.error("Timed out waiting for Roll Call page to load.")
        logger.error("This may indicate network issues or changes to the Roll Call interface.")
        return False
        
    except Exception as e:
        logger.error(f"Error during form submission: {e}")
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """
    Main execution flow for the attendance export script.
    
    This function orchestrates the entire process and ensures cleanup
    happens even if errors occur mid-execution.
    """
    # Initialize logging
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("Canvas Roll Call Attendance Export - Starting")
    logger.info("=" * 60)
    
    # Validate configuration
    if not ADMIN_API_TOKEN or not USER_ID or "yourschool" in BASE_URL:
        logger.error("Configuration incomplete! Please update the following in the script:")
        logger.error("  - ADMIN_API_TOKEN")
        logger.error("  - USER_ID")
        logger.error("  - BASE_URL")
        logger.error("  - REPORT_EMAIL")
        sys.exit(1)
    
    # Track resources for cleanup
    temp_token_id = None
    driver = None
    success = False
    
    try:
        # Step 1: Create temporary token
        temp_token, temp_token_id = create_temporary_token(logger)
        
        # Step 2: Get sessionless launch URL
        sessionless_url = get_sessionless_launch_url(temp_token, logger)
        if not sessionless_url:
            logger.error("Could not obtain sessionless URL. Aborting.")
            sys.exit(1)
        
        # Step 3: Calculate date range
        start_date, end_date = calculate_date_range()
        today = datetime.now()
        day_name = today.strftime("%A")
        logger.info(f"Today is {day_name}. Report date range: {start_date} to {end_date}")
        
        # Step 4: Initialize browser and submit form
        driver = configure_chrome_driver(logger)
        success = submit_attendance_report_form(driver, start_date, end_date, sessionless_url, logger)
        
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user.")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        
    finally:
        # Cleanup: Always try to close browser and delete token
        if driver:
            logger.info("Closing browser...")
            try:
                driver.quit()
            except Exception:
                pass  # Best effort
        
        if temp_token_id:
            delete_temporary_token(temp_token_id, logger)
    
    # Final status
    logger.info("=" * 60)
    if success:
        logger.info("SUCCESS - Attendance report requested")
        logger.info(f"Report will be emailed to: {REPORT_EMAIL}")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("FAILED - Attendance report was not requested")
        logger.info("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
