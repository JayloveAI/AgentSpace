"""Sidecar gateway and auto-routing utilities."""

from .auto_catcher import auto_catch_and_route, ResourceMissingError
from .router import UniversalResourceGateway

__all__ = ["auto_catch_and_route", "ResourceMissingError", "UniversalResourceGateway"]
