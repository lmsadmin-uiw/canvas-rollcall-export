# Canvas Roll Call Attendance Export

Automated extraction of attendance data from Canvas LMS via the Roll Call Attendance tool.

## Overview

This script automates the process of requesting attendance reports from Canvas Roll Call. Since Roll Call does not provide a direct API for report generation, and the tool is kind of garbage sometimes, this script uses Selenium to automate the browser-based form submission.

### What It Does

1. Creates a temporary Canvas API token (expires in 1 hour after creation)
2. Generates a sessionless launch URL for Roll Call
3. Uses headless Chrome to fill out and submit the report request form
4. Cleans up the temporary token
5. Roll Call emails the report CSV to your configured address

### Scheduling Logic

The script is designed to run daily as a scheduled task:

| Day | Behavior | Rationale |
|-----|----------|-----------|
| Monday | Pulls previous 7 days | Captures attendance entered over the weekend |
| Tue-Sun | Pulls previous day only | Daily incremental export |

---

## Prerequisites

### 1. Python 3.7+

Check your version:
```bash
python3 --version
```

### 2. Google Chrome Browser

**Linux (Ubuntu/Debian):**
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f  # Fix any dependency issues
```

**Linux (RHEL/CentOS):**
```bash
sudo dnf install https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
```

**macOS:**
```bash
brew install --cask google-chrome
```

**Windows:**
Download from https://www.google.com/chrome/

### 3. ChromeDriver

ChromeDriver must match your Chrome version. Check your Chrome version first:
```bash
google-chrome --version
# or on macOS:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version
```

**Option A: Automatic Management (Recommended)**

The `webdriver-manager` package handles this automatically. It's included in the requirements.

**Option B: Manual Installation**

1. Find your Chrome version (e.g., 120.0.6099.109)
2. Download matching ChromeDriver from: https://googlechromelabs.github.io/chrome-for-testing/
3. Place in system PATH or same directory as script

### 4. Python Packages

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install requests selenium webdriver-manager
```

---

## Installation

### 1. Clone or Download

```bash
# Create directory - Name directory or file(s) whatever you'd like
mkdir canvas_attendance_export
cd canvas_attendance_export

# Copy the script files here
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the Script

Open `attendance_export.py` and update the configuration section:

```python
# Canvas API Configuration
ADMIN_API_TOKEN = "your_token_here"  # From Canvas profile settings
USER_ID = "12345"                     # Canvas user ID for token owner
BASE_URL = "https://yourschool.instructure.com/api/v1"

# Email for report delivery
REPORT_EMAIL = "canvas-admin@yourschool.edu"
```

#### Finding Your Configuration Values

**ADMIN_API_TOKEN:**
1. Log into Canvas as an admin user
2. Go to Account → Settings (or Profile → Settings)
3. Scroll to "Approved Integrations"
4. Click "+ New Access Token"
5. Enter a purpose (e.g., "Attendance Export Script")
6. Copy the token immediately (it won't be shown again)

**USER_ID:**
1. In Canvas, go to the profile of the user who created the token
2. Look at the URL: `https://yourschool.instructure.com/users/12345`
3. The number at the end is the USER_ID

**ACCOUNT_ID:**
- Usually "1" for the root account, this is where the Roll Call Report will be generated
- Check your account URL: `https://yourschool.instructure.com/accounts/1`

### 4. Test the Script

```bash
python3 attendance_export.py
```

You should see output like:
```
[2024-12-15 08:00:00] INFO - Canvas Roll Call Attendance Export - Starting
[2024-12-15 08:00:01] INFO - Creating temporary API token...
[2024-12-15 08:00:01] INFO - Temporary token created successfully
[2024-12-15 08:00:02] INFO - Generating Roll Call sessionless launch URL...
[2024-12-15 08:00:02] INFO - Sessionless launch URL retrieved successfully
[2024-12-15 08:00:02] INFO - Today is Monday. Report date range: 12/09/2024 to 12/15/2024
[2024-12-15 08:00:03] INFO - Initializing headless Chrome browser...
[2024-12-15 08:00:05] INFO - Filling report form...
[2024-12-15 08:00:10] INFO - Form submitted successfully
[2024-12-15 08:00:10] INFO - Cleaning up temporary token...
[2024-12-15 08:00:11] INFO - SUCCESS - Attendance report requested
```

---

## Scheduling

### Linux (cron)

```bash
# Edit crontab
crontab -e

# Add entry to run daily at 6:00 AM
0 6 * * * /usr/bin/python3 /path/to/attendance_export.py >> /var/log/attendance_export.log 2>&1
```

**With virtual environment:**
```bash
0 6 * * * /path/to/venv/bin/python /path/to/attendance_export.py >> /var/log/attendance_export.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at desired time
4. Set action: Start a program
   - Program: `python` (or full path to python.exe)
   - Arguments: `C:\path\to\attendance_export.py`
   - Start in: `C:\path\to\`
5. Check "Run whether user is logged on or not"

### macOS (launchd)

Create `~/Library/LaunchAgents/com.yourschool.attendance-export.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourschool.attendance-export</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/attendance_export.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/attendance_export.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/attendance_export.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.yourschool.attendance-export.plist
```

---

## Configuration Options

### Logging

To enable file logging (recommended for scheduled tasks):

```python
ENABLE_FILE_LOGGING = True
LOG_FILE_PATH = "/var/log/attendance_export.log"  # Or your preferred path
```

### Multiple Email Recipients

To send the report to multiple addresses:

```python
REPORT_EMAIL = "admin1@school.edu, admin2@school.edu, registrar@school.edu"
```

### Timeouts

Adjust if experiencing timeout issues:

```python
PAGE_LOAD_TIMEOUT = 30      # Seconds to wait for page load
FORM_SUBMIT_WAIT = 5        # Seconds to wait after submission
ELEMENT_WAIT_TIMEOUT = 10   # Seconds to wait for form elements
```

---

## Troubleshooting

### "Failed to create token"

- Verify `ADMIN_API_TOKEN` is correct and not expired
- Ensure the token owner has admin permissions
- Check `USER_ID` matches the token owner

### "Failed to get sessionless URL"

- Verify `ACCOUNT_ID` is correct
- Ensure Roll Call is installed and enabled for your account
- Check that the token owner can access Roll Call manually

### "Failed to initialize Chrome WebDriver"

- Ensure Chrome is installed: `google-chrome --version`
- Ensure ChromeDriver is installed and matches Chrome version
- On Linux, you may need: `sudo apt-get install chromium-chromedriver`

### "Timed out waiting for Roll Call page"

- Check network connectivity
- Roll Call service may be temporarily unavailable
- Try increasing `PAGE_LOAD_TIMEOUT`

### Form submission errors

- Roll Call interface may have changed
- Check the Roll Call page manually to verify form field names
- Contact Instructure support if the interface has changed

---

## Security Considerations

1. **Token Security**: The script creates a temporary token that expires in 1 hour. Even if the script fails, the token will auto-expire.

2. **Credentials**: Store `ADMIN_API_TOKEN` securely. Consider using environment variables for production:
   ```python
   import os
   ADMIN_API_TOKEN = os.environ.get("CANVAS_API_TOKEN")
   ```

3. **Permissions**: The Canvas account used should have minimal necessary permissions (ability to launch Roll Call and create tokens).

4. **Log Files**: If logging to file, ensure appropriate permissions to prevent unauthorized access to log data.

---

## Expected File Structure

```
canvas_attendance_export/
├── attendance_export.py    # Main script
├── requirements.txt        # Python dependencies
├── README.md              # This documentation
└── attendance_export.log  # Log file (if enabled)
```

---

## Support

For issues related to:
- **Roll Call**: Contact Instructure support
- **Canvas API**: See [Canvas API Documentation](https://developerdocs.instructure.com/services/canvas/resources)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | Dec 2025 | Refactored with improved error handling, logging, documentation prior to sharing |
| 1.0 | Jan 2025 | Initial working version, flaws and all |

---

## License

This script is provided as-is for educational institutions using Canvas LMS. Modify and distribute as needed for your institution's requirements.
