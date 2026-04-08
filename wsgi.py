"""
WSGI entry for Gunicorn on the VM.
Initializes the DB pool before the Flask app handles traffic.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# Ensure app runs with install dir as cwd so data/, classifier.xml, static/ resolve.
_root = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _root:
    os.chdir(_root)

from database import Database  # noqa: E402

try:
    Database.initialize_pool()
    Database.create_tables()
except Exception as e:
    logging.getLogger(__name__).exception("Database startup failed: %s", e)
    raise

from app import app as application  # noqa: E402

app = application
