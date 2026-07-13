"""ASGI entrypoint."""

from resume_matcher.app import create_app

app = create_app()
