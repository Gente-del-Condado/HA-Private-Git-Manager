import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "private_git_manager"))
os.environ["PGM_DEV"] = "1"
os.environ["PGM_DATA"] = tempfile.mkdtemp(prefix="pgm-api-test-")
os.environ["PGM_ADDONS"] = tempfile.mkdtemp(prefix="pgm-addons-test-")
