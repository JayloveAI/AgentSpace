"""Discovery utilities for clawhub configuration."""

from .config_scraper import generate_config
from .skill_scanner import scan_skills

__all__ = ["generate_config", "scan_skills"]
