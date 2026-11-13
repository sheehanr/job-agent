"""Loads the config/ folder and environment settings."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from tracker.sources.simplify import normalize

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("JOB_AGENT_CONFIG", ROOT / "config"))

load_dotenv(ROOT / ".env")


@dataclass
class Company:
    name: str
    aliases: list = field(default_factory=list)
    site: dict | None = None

    @property
    def keys(self):
        return {normalize(n) for n in [self.name, *self.aliases]}


@dataclass
class Config:
    settings: dict
    companies: list
    blocked_companies: set
    blocked_categories: list
    profile: str

    def company_for(self, name):
        """The configured Company matching a posting's company name, or None."""

        key = normalize(name)
        return self._by_key.get(key)

    def display_name(self, name):
        company = self.company_for(name)
        return company.name if company else (name or "").strip()

    def is_blocked(self, name):
        return normalize(name) in self.blocked_companies

    def __post_init__(self):
        self._by_key = {}
        for company in self.companies:
            for key in company.keys:
                self._by_key[key] = company


def _yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load(config_dir=CONFIG_DIR):

    config_dir = Path(config_dir)

    settings = _yaml(config_dir / "settings.yaml")
    companies = [
        Company(
            name=c["name"],
            aliases=c.get("aliases") or [],
            site=c.get("site"),
        )
        for c in _yaml(config_dir / "companies.yaml").get("companies", [])
    ]
    blocklist = _yaml(config_dir / "blocklist.yaml")

    return Config(
        settings=settings,
        companies=companies,
        blocked_companies={normalize(n) for n in blocklist.get("companies") or []},
        blocked_categories=blocklist.get("categories") or [],
        profile=(config_dir / "profile.md").read_text(),
    )


def env(name, default=None, required=False):

    value = os.environ.get(name, default)

    if required and not value:
        raise RuntimeError(f"Missing environment variable {name}")

    return value
