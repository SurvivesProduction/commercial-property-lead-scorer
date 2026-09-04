"""Abstract base classes every portal-specific scraper implements.

Two base classes, not one, because this tool cross-references two
independently-scraped source types (property assessment records and
permit records) -- see `leadscorer.normalize.schema`. Both follow the
same fetch -> parse -> normalize -> yield shape as Tool 1's `BaseScraper`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from leadscorer.normalize.schema import PermitRecord, PropertyRecord


class BasePropertyScraper(ABC):
    """Fetch -> parse -> normalize -> yield pipeline for a property-assessment source.

    Concrete subclasses live in a downstream package (e.g. the paid
    per-client deployment) and are parametrized per portal / client. This
    class has no knowledge of any specific scraping target.
    """

    def __init__(self, client_id: str, source: str) -> None:
        self.client_id = client_id
        self.source = source

    @abstractmethod
    def fetch(self) -> Any:
        """Retrieve the raw content for this source (HTML, JSON, CSV, etc.)."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: Any) -> list[dict[str, Any]]:
        """Parse raw fetched content into a list of raw record dicts."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_record: dict[str, Any]) -> PropertyRecord:
        """Convert a single raw record dict into a `PropertyRecord`."""
        raise NotImplementedError

    def run(self) -> Iterator[PropertyRecord]:
        """Orchestrate fetch -> parse -> normalize -> yield `PropertyRecord` records."""
        raw = self.fetch()
        for raw_record in self.parse(raw):
            yield self.normalize(raw_record)


class BasePermitScraper(ABC):
    """Fetch -> parse -> normalize -> yield pipeline for a permit-history source."""

    def __init__(self, client_id: str, source: str) -> None:
        self.client_id = client_id
        self.source = source

    @abstractmethod
    def fetch(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_record: dict[str, Any]) -> PermitRecord:
        raise NotImplementedError

    def run(self) -> Iterator[PermitRecord]:
        """Orchestrate fetch -> parse -> normalize -> yield `PermitRecord` records."""
        raw = self.fetch()
        for raw_record in self.parse(raw):
            yield self.normalize(raw_record)
