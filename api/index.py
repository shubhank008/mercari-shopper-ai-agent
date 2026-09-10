"""Vercel serverless entry point for the shared ASGI application."""

from src.web.app import app

__all__ = ["app"]
