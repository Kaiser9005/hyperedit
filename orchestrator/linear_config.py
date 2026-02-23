"""
Linear Configuration
====================

Configuration constants for Linear integration.
These values are used in prompts and for project state management.
"""

import os

# Environment variables (must be set before running)
LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY")

# Default number of issues to create (can be overridden via command line)
DEFAULT_ISSUE_COUNT = 50

# Issue status workflow (Linear default states)
STATUS_TODO = "Todo"
STATUS_IN_PROGRESS = "In Progress"
STATUS_DONE = "Done"

# Label categories (map to feature types)
LABEL_FUNCTIONAL = "functional"
LABEL_STYLE = "style"
LABEL_INFRASTRUCTURE = "infrastructure"

# Priority mapping (Linear uses 0-4 where 1=Urgent, 4=Low, 0=No priority)
PRIORITY_URGENT = 1
PRIORITY_HIGH = 2
PRIORITY_MEDIUM = 3
PRIORITY_LOW = 4

# Local marker file to track Linear project initialization
LINEAR_PROJECT_MARKER = ".linear_project.json"

# Meta issue title for project tracking and session handoff
META_ISSUE_TITLE = "[META] Project Progress Tracker"

# Timeout Configuration (in seconds)
# These are used in prompts to guide agent behavior
TIMEOUT_BASH_COMMAND = 30
TIMEOUT_GIT_PUSH = 60
TIMEOUT_NPM_BUILD = 180
TIMEOUT_NPM_TYPECHECK = 120
TIMEOUT_BROWSER_NAV = 30
TIMEOUT_E2E_SUITE = 600

# BashOutput retry limits (to prevent infinite loops)
MAX_BASH_OUTPUT_RETRIES = 5
MAX_GIT_PUSH_RETRIES = 3

# E2E Test Configuration
E2E_WORKERS = 1
E2E_TIMEOUT_MS = 90000
E2E_BASE_URL = "http://localhost:8080"

# Git Configuration
GIT_PUSH_NO_VERIFY = True
GIT_SKIP_PUSH_ON_TIMEOUT = True
