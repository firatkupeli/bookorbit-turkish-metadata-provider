"""CI-only server for the upstream checker. Never included in the Docker image."""

from app.api import create_app
from app.config import Settings
from tests.conftest import make_source_transport

transport, _calls = make_source_transport()
app = create_app(Settings(_env_file=None, source_interval_seconds=0), transport)
