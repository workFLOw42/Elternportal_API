"""API client for ElternPortal."""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL_TEMPLATE, ENDPOINT_LOGIN, ENDPOINT_LOGOUT

_LOGGER = logging.getLogger(__name__)


class ElternPortalApiError(Exception):
    """General API error."""


class ElternPortalAuthError(ElternPortalApiError):
    """Authentication error."""


class ElternPortalApi:
    """API client for ElternPortal."""

    def __init__(
        self,
        school_slug: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize."""
        self._school_slug = school_slug
        self._username = username
        self._password = password
        self._base_url = BASE_URL_TEMPLATE.format(school_slug)
        self._session: aiohttp.ClientSession | None = None
        self._logged_in = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return an active session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar()
            )
            self._logged_in = False
        return self._session

    async def _get_csrf_token(self, session: aiohttp.ClientSession) -> str:
        """Fetch CSRF token from the login page."""
        async with session.get(self._base_url) as resp:
            if resp.status != 200:
                raise ElternPortalApiError(
                    f"Failed to load login page: HTTP {resp.status}"
                )
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        csrf_input = soup.find("input", {"name": "csrf"})
        if csrf_input and csrf_input.get("value"):
            return csrf_input["value"]
        csrf_meta = soup.find("meta", {"name": "csrf-token"})
        if csrf_meta and csrf_meta.get("content"):
            return csrf_meta["content"]
        raise ElternPortalApiError("CSRF token not found")

    async def login(self) -> None:
        """Log in to ElternPortal."""
        session = await self._get_session()

        try:
            csrf = await self._get_csrf_token(session)
        except Exception as err:
            raise ElternPortalAuthError(
                f"Failed to obtain CSRF token: {err}"
            ) from err

        payload = {
            "csrf": csrf,
            "username": self._username,
            "password": self._password,
            "go_to": "",
        }

        try:
            async with session.post(
                f"{self._base_url}{ENDPOINT_LOGIN}",
                data=payload,
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    raise ElternPortalAuthError(
                        f"Login returned HTTP {resp.status}"
                    )
                body = await resp.text()
                if "Benutzername oder Kennwort sind nicht korrekt" in body:
                    raise ElternPortalAuthError("Invalid credentials")
                if "login" in str(resp.url).lower() and "username" in body.lower():
                    raise ElternPortalAuthError("Login failed")
        except aiohttp.ClientError as err:
            raise ElternPortalAuthError(
                f"Connection error during login: {err}"
            ) from err

        self._logged_in = True
        _LOGGER.debug("Logged in to ElternPortal (%s)", self._school_slug)

    async def _ensure_logged_in(self) -> None:
        """Make sure we have a valid session."""
        if not self._logged_in:
            await self.login()

    async def _fetch_page(self, path: str) -> str:
        """Fetch an HTML page (re-login on redirect to login)."""
        await self._ensure_logged_in()
        session = await self._get_session()
        url = f"{self._base_url}{path}"

        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise ElternPortalApiError(f"HTTP {resp.status} for {path}")
                html = await resp.text()
                if "login" in str(resp.url).lower() and "username" in html.lower():
                    self._logged_in = False
                    await self.login()
                    async with session.get(url, allow_redirects=True) as retry:
                        return await retry.text()
                return html
        except aiohttp.ClientError as err:
            raise ElternPortalApiError(f"Connection error: {err}") from err

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    async def get_letters(self) -> list[dict[str, Any]]:
        """Fetch Elternbriefe."""
        html = await self._fetch_page("/aktuelles/elternbriefe")
        return self._parse_table_or_list(html)

    async def get_blackboard(self) -> list[dict[str, Any]]:
        """Fetch Schwarzes Brett."""
        html = await self._fetch_page("/aktuelles/schwarzes_brett")
        return self._parse_cards(html)

    async def get_appointments(self) -> list[dict[str, Any]]:
        """Fetch Termine."""
        html = await self._fetch_page("/aktuelles/termine")
        return self._parse_table_or_list(html)

    async def get_messages(self) -> list[dict[str, Any]]:
        """Fetch Nachrichten / Kommunikation."""
        html = await self._fetch_page("/meldungen/kommunikation_f498")
        return self._parse_table_or_list(html)

    async def get_substitution(self) -> list[dict[str, Any]]:
        """Fetch Vertretungsplan."""
        html = await self._fetch_page("/aktuelles/vertretungsplan")
        return self._parse_table_rows(html)

    async def get_timetable(self) -> list[dict[str, Any]]:
        """Fetch Stundenplan."""
        html = await self._fetch_page("/service/stundenplan")
        return self._parse_timetable(html)

    async def get_children(self) -> list[dict[str, Any]]:
        """Fetch Kinder."""
        html = await self._fetch_page("/service/kinder")
        return self._parse_children(html)

    # ------------------------------------------------------------------

    def _parse_table_or_list(self, html: str) -> list[dict[str, Any]]:
        """Parse a page that is either a <table> or card/list layout."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        rows = soup.select("table tbody tr")
        if rows:
            headers = [
                th.get_text(strip=True)
                for th in soup.select("table thead th, table thead td")
            ]
            for row in rows:
                cols = row.find_all("td")
                entry: dict[str, Any] = {}
                for idx, col in enumerate(cols):
                    key = headers[idx] if idx < len(headers) else f"col_{idx}"
                    entry[key] = col.get_text(strip=True)
                link = row.select_one("a[href]")
                if link:
                    entry["link"] = link["href"]
                if entry:
                    items.append(entry)
            return items

        # Fallback: card / list-group layout
        cards = soup.select(
            ".list-group-item, .card, .panel, .well, .row.mb-2, .row.mb-3"
        )
        for card in cards:
            entry = {}
            title_el = card.select_one("h3, h4, h5, strong, b, .title")
            if title_el:
                entry["title"] = title_el.get_text(strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            body_el = card.select_one(".card-body, .panel-body, p, .content")
            if body_el:
                entry["content"] = body_el.get_text(strip=True)
            link = card.select_one("a[href]")
            if link:
                entry["link"] = link["href"]
            if entry.get("title") or entry.get("content"):
                items.append(entry)

        return items

    def _parse_cards(self, html: str) -> list[dict[str, Any]]:
        """Parse card / blackboard style entries."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        cards = soup.select(
            ".card, .panel, .well, .list-group-item, .row.mb-2, .row.mb-3"
        )
        for card in cards:
            entry: dict[str, Any] = {}
            title_el = card.select_one("h3, h4, h5, strong, b, .title")
            if title_el:
                entry["title"] = title_el.get_text(strip=True)
            body_el = card.select_one(".card-body, .panel-body, p, .content")
            if body_el:
                entry["content"] = body_el.get_text(strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            if entry.get("title") or entry.get("content"):
                items.append(entry)

        if not items:
            return self._parse_table_or_list(html)

        return items

    def _parse_table_rows(self, html: str) -> list[dict[str, Any]]:
        """Parse generic table rows (substitution plan etc.)."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []
        headers = [
            th.get_text(strip=True)
            for th in soup.select("table thead th, table thead td")
        ]
        for row in soup.select("table tbody tr"):
            cols = row.find_all("td")
            entry: dict[str, Any] = {}
            for idx, col in enumerate(cols):
                key = headers[idx] if idx < len(headers) else f"col_{idx}"
                entry[key] = col.get_text(strip=True)
            if entry:
                items.append(entry)
        return items

    def _parse_timetable(self, html: str) -> list[dict[str, Any]]:
        """Parse Stundenplan table."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table")
        if not table:
            return []

        headers: list[str] = []
        header_row = table.select_one("thead tr, tr:first-child")
        if header_row:
            headers = [
                th.get_text(strip=True) for th in header_row.find_all(["th", "td"])
            ]

        items: list[dict[str, Any]] = []
        body_rows = table.select("tbody tr")
        if not body_rows:
            body_rows = table.select("tr")[1:]
        for row in body_rows:
            cols = row.find_all("td")
            entry: dict[str, Any] = {}
            for idx, col in enumerate(cols):
                key = headers[idx] if idx < len(headers) else f"col_{idx}"
                entry[key] = col.get_text(strip=True)
            if entry:
                items.append(entry)
        return items

    def _parse_children(self, html: str) -> list[dict[str, Any]]:
        """Parse Kinder page."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        options = soup.select("select option")
        for opt in options:
            name = opt.get_text(strip=True)
            value = opt.get("value", "")
            if name and value:
                items.append({"name": name, "id": value})
        if items:
            return items

        cards = soup.select(".card, .panel, .list-group-item")
        for card in cards:
            name_el = card.select_one("h4, h5, strong, .name")
            if name_el:
                entry: dict[str, Any] = {"name": name_el.get_text(strip=True)}
                cls_el = card.select_one(".class, .klasse, small")
                if cls_el:
                    entry["class"] = cls_el.get_text(strip=True)
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Aggregated fetch
    # ------------------------------------------------------------------

    async def get_all_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all endpoints and return combined dict."""
        data: dict[str, list[dict[str, Any]]] = {
            "letters": [],
            "blackboard": [],
            "appointments": [],
            "messages": [],
            "substitution": [],
            "timetable": [],
            "children": [],
        }

        fetchers = {
            "letters": self.get_letters,
            "blackboard": self.get_blackboard,
            "appointments": self.get_appointments,
            "messages": self.get_messages,
            "substitution": self.get_substitution,
            "timetable": self.get_timetable,
            "children": self.get_children,
        }

        for key, fetcher in fetchers.items():
            try:
                data[key] = await fetcher()
            except ElternPortalApiError as err:
                _LOGGER.warning("Failed to fetch %s: %s", key, err)

        return data

    # ------------------------------------------------------------------
    # Connection test & cleanup
    # ------------------------------------------------------------------

    async def test_connection(self) -> bool:
        """Test credentials."""
        try:
            await self.login()
            return True
        except ElternPortalAuthError:
            return False
        except ElternPortalApiError:
            return False

    async def close(self) -> None:
        """Close session."""
        if self._session and not self._session.closed:
            try:
                await self._session.get(f"{self._base_url}{ENDPOINT_LOGOUT}")
            except Exception:  # noqa: BLE001
                pass
            await self._session.close()
            self._session = None
            self._logged_in = False