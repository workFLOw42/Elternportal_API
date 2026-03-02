"""API client for ElternPortal."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    BASE_URL_TEMPLATE,
    ENDPOINT_LOGIN,
    ENDPOINT_LOGOUT,
    PATH_SCHOOL_INFO,
    PATH_TIMETABLE,
    PATH_EXAMS,
    PATH_APPOINTMENTS,
    PATH_BLACKBOARD,
    PATH_LETTERS,
    PATH_MESSAGES,
    PATH_CHILDREN,
)

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
    # Schulinformationen
    # ------------------------------------------------------------------

    async def get_school_info(self) -> list[dict[str, Any]]:
        """Fetch /service/schulinformationen."""
        html = await self._fetch_page(PATH_SCHOOL_INFO)
        return self._parse_school_info(html)

    def _parse_school_info(self, html: str) -> list[dict[str, Any]]:
        """Parse school information page."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        rows = soup.select("table tbody tr")
        if rows:
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    items.append({
                        "label": cols[0].get_text(strip=True),
                        "value": cols[1].get_text(strip=True),
                    })
            return items

        dts = soup.select("dt")
        dds = soup.select("dd")
        for dt, dd in zip(dts, dds):
            items.append({
                "label": dt.get_text(strip=True),
                "value": dd.get_text(strip=True),
            })
        if items:
            return items

        sections = soup.select(".card, .panel, .well, .row, .col")
        for section in sections:
            title_el = section.select_one("h3, h4, h5, strong, b, .title, label")
            content_el = section.select_one("p, span, .content, .value, td")
            if title_el:
                entry: dict[str, Any] = {"label": title_el.get_text(strip=True)}
                if content_el and content_el != title_el:
                    entry["value"] = content_el.get_text(strip=True)
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Stundenplan
    # ------------------------------------------------------------------

    async def get_timetable(self) -> list[dict[str, Any]]:
        """Fetch /service/stundenplan."""
        html = await self._fetch_page(PATH_TIMETABLE)
        return self._parse_timetable(html)

    def _parse_timetable(self, html: str) -> list[dict[str, Any]]:
        """Parse timetable table."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table")
        if not table:
            return []

        headers: list[str] = []
        header_row = table.select_one("thead tr")
        if not header_row:
            header_row = table.select_one("tr:first-child")
        if header_row:
            headers = [
                th.get_text(strip=True) for th in header_row.find_all(["th", "td"])
            ]

        items: list[dict[str, Any]] = []
        body_rows = table.select("tbody tr")
        if not body_rows:
            all_rows = table.select("tr")
            body_rows = all_rows[1:] if len(all_rows) > 1 else []

        for row in body_rows:
            cols = row.find_all(["td", "th"])
            entry: dict[str, Any] = {}
            for idx, col in enumerate(cols):
                key = headers[idx] if idx < len(headers) else f"col_{idx}"
                lines = [line.strip() for line in col.stripped_strings]
                entry[key] = " | ".join(lines) if lines else ""
            if entry:
                items.append(entry)
        return items

    # ------------------------------------------------------------------
    # Schulaufgaben
    # ------------------------------------------------------------------

    async def get_exams(self) -> list[dict[str, Any]]:
        """Fetch /service/termine/liste/schulaufgaben."""
        html = await self._fetch_page(PATH_EXAMS)
        return self._parse_termine(html)

    # ------------------------------------------------------------------
    # Allgemeine Termine
    # ------------------------------------------------------------------

    async def get_appointments(self) -> list[dict[str, Any]]:
        """Fetch /service/termine/liste/allgemein."""
        html = await self._fetch_page(PATH_APPOINTMENTS)
        return self._parse_termine(html)

    def _parse_termine(self, html: str) -> list[dict[str, Any]]:
        """Parse Termine pages (Schulaufgaben + Allgemein)."""
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
                if entry:
                    items.append(entry)
            return items

        current_month = ""
        for el in soup.select("h3, h4, h5, .list-group-item, tr, .termin, .event, li"):
            tag = el.name
            if tag in ("h3", "h4", "h5"):
                current_month = el.get_text(strip=True)
                continue

            text = el.get_text(strip=True)
            if not text:
                continue

            entry = {"month": current_month}
            date_el = el.select_one("small, .text-muted, .date, time, .datum")
            title_el = el.select_one("strong, b, .title, .name, .bezeichnung")

            if date_el and title_el:
                entry["date"] = date_el.get_text(strip=True)
                entry["title"] = title_el.get_text(strip=True)
            elif date_el:
                entry["date"] = date_el.get_text(strip=True)
                remaining = text.replace(entry["date"], "").strip()
                entry["title"] = remaining
            else:
                entry["title"] = text

            badge = el.select_one(".badge, .label, .kategorie, .fach")
            if badge:
                entry["subject"] = badge.get_text(strip=True)

            if entry.get("title"):
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Schwarzes Brett
    # ------------------------------------------------------------------

    async def get_blackboard(self) -> list[dict[str, Any]]:
        """Fetch /aktuelles/schwarzes_brett."""
        html = await self._fetch_page(PATH_BLACKBOARD)
        return self._parse_blackboard(html)

    def _parse_blackboard(self, html: str) -> list[dict[str, Any]]:
        """Parse Schwarzes Brett."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        cards = soup.select(
            ".card, .panel, .well, .list-group-item, .row.mb-2, .row.mb-3"
        )
        for card in cards:
            entry: dict[str, Any] = {}
            title_el = card.select_one("h3, h4, h5, strong, b, .title, .card-title")
            if title_el:
                entry["title"] = title_el.get_text(strip=True)
            body_el = card.select_one(
                ".card-body, .card-text, .panel-body, p, .content"
            )
            if body_el:
                entry["content"] = body_el.get_text(separator="\n", strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            if entry.get("title") or entry.get("content"):
                items.append(entry)

        if not items:
            rows = soup.select("table tbody tr")
            for row in rows:
                cols = row.find_all("td")
                entry = {}
                if len(cols) >= 1:
                    entry["title"] = cols[0].get_text(strip=True)
                if len(cols) >= 2:
                    entry["content"] = cols[1].get_text(strip=True)
                if len(cols) >= 3:
                    entry["date"] = cols[2].get_text(strip=True)
                if entry:
                    items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Elternbriefe
    # ------------------------------------------------------------------

    async def get_letters(self) -> list[dict[str, Any]]:
        """Fetch /aktuelles/elternbriefe."""
        html = await self._fetch_page(PATH_LETTERS)
        return self._parse_letters(html)

    def _parse_letters(self, html: str) -> list[dict[str, Any]]:
        """Parse Elternbriefe."""
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
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"{self._base_url}{href}"
                    entry["link"] = href
                entry["new"] = bool(
                    row.select_one(".badge, .label-danger, .new, .unread")
                ) or "neu" in row.get_text().lower()
                if entry:
                    items.append(entry)
            return items

        cards = soup.select(".list-group-item, .card, .panel, .elternbrief")
        for card in cards:
            entry = {}
            title_el = card.select_one("h4, h5, strong, b, .title, a")
            if title_el:
                entry["title"] = title_el.get_text(strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            link = card.select_one("a[href]")
            if link:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self._base_url}{href}"
                entry["link"] = href
            entry["new"] = bool(
                card.select_one(".badge, .label-danger, .new, .unread")
            ) or "neu" in card.get_text().lower()
            if entry.get("title"):
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Kommunikation Fachlehrer
    # ------------------------------------------------------------------

    async def get_messages(self) -> list[dict[str, Any]]:
        """Fetch /meldungen/kommunikation_fachlehrer."""
        html = await self._fetch_page(PATH_MESSAGES)
        return self._parse_messages(html)

    def _parse_messages(self, html: str) -> list[dict[str, Any]]:
        """Parse Kommunikation Fachlehrer."""
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
                entry["unread"] = bool(
                    row.select_one(".badge, .unread, .font-weight-bold, strong, .new")
                )
                link = row.select_one("a[href]")
                if link:
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"{self._base_url}{href}"
                    entry["link"] = href
                if entry:
                    items.append(entry)
            return items

        cards = soup.select(
            ".list-group-item, .card, .panel, .message, .nachricht"
        )
        for card in cards:
            entry: dict[str, Any] = {}
            subject_el = card.select_one(
                "h4, h5, strong, b, .title, .subject, .betreff"
            )
            if subject_el:
                entry["subject"] = subject_el.get_text(strip=True)
            sender_el = card.select_one(".sender, .from, .absender, .teacher")
            if sender_el:
                entry["sender"] = sender_el.get_text(strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            entry["unread"] = bool(
                card.select_one(".badge, .unread, .font-weight-bold, .new")
            )
            link = card.select_one("a[href]")
            if link:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self._base_url}{href}"
                entry["link"] = href
            if entry.get("subject") or entry.get("sender"):
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Kinder
    # ------------------------------------------------------------------

    async def get_children(self) -> list[dict[str, Any]]:
        """Fetch /service/kinder."""
        html = await self._fetch_page(PATH_CHILDREN)
        return self._parse_children(html)

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
            "school_info": [],
            "timetable": [],
            "exams": [],
            "appointments": [],
            "blackboard": [],
            "letters": [],
            "messages": [],
            "children": [],
        }

        fetchers = {
            "school_info": self.get_school_info,
            "timetable": self.get_timetable,
            "exams": self.get_exams,
            "appointments": self.get_appointments,
            "blackboard": self.get_blackboard,
            "letters": self.get_letters,
            "messages": self.get_messages,
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