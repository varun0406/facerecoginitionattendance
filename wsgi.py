"""
WSGI entry for Gunicorn on the VM.
App import initializes the database before the background sync thread runs.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

_root = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _root:
    os.chdir(_root)

from app import app as application  # noqa: E402

app = application
