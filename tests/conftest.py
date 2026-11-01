"""Test-wide configuration.

Tracing is disabled for the suite. The ConsoleSpanExporter writes to
stdout from a BatchSpanProcessor background thread, and pytest closes
its captured stdout at the end of the session, so a flush arriving
afterwards raises "I/O operation on closed file".

This must run before anything imports app.config, which reads the
environment once at import time. conftest is imported before test
modules, so setting it here is early enough.
"""
import os

os.environ["OTEL_ENABLED"] = "false"
