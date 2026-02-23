"""Root conftest.py — adds services/ to sys.path for pytest discovery."""

import sys
from pathlib import Path

# Add services/ to Python path so bare imports (e.g., from skill_dead_air import ...)
# resolve correctly when pytest is run from the project root.
services_dir = Path(__file__).parent / "services"
if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))
