"""API client for ElternPortal."""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup, Tag

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
    PATH_SURVEYS,
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
        self._child_name: str | None = None
        self._class_name: str | None = None
        self._children: list[dict[str, str]] = []

    @property
    def child_name(self) -> str | None:
        """Return detected child name."""
        return self._child_name

    @property
    def class_name(self) -> str | None:
        """Return detected class name."""
        return self._class_name

    @property
    def children(self) -> list[dict[str, str]]:
        """Return detected children."""
        return self._children

    # ------------------------------------------------------------------
    # Session & Auth
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return an active session with timeout."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(),
                timeout=timeout,
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
                if (
                    "login" in str(resp.url).lower()
                    and "username" in body.lower()
                ):
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
                    raise ElternPortalApiError(
                        f"HTTP {resp.status} for {path}"
                    )
                html = await resp.text()
                if (
                    "login" in str(resp.url).lower()
                    and "username" in html.lower()
                ):
                    _LOGGER.debug(
                        "Session expired, re-logging in for %s", path
                    )
                    self._logged_in = False
                    await self.login()
                    async with session.get(
                        url, allow_redirects=True
                    ) as retry:
                        return await retry.text()
                return html
        except aiohttp.ClientError as err:
            raise ElternPortalApiError(f"Connection error: {err}") from err

    # ------------------------------------------------------------------
    # Child detection from navigation
    # ------------------------------------------------------------------

    def _extract_children_from_html(self, html: str) -> None:
        """Extract children info from the pupil-selector dropdown."""
        soup = BeautifulSoup(html, "html.parser")
        select = soup.select_one(".pupil-selector select")
        if not select:
            return

        self._children = []
        for opt in select.find_all("option"):
            text = opt.get_text(strip=True)
            value = opt.get("value", "")
            if not text or not value:
                continue
            match = re.match(r"^(.+?)\s*\((\w+)\)$", text)
            if match:
                name = match.group(1).strip()
                cls = match.group(2).strip()
                self._children.append(
                    {"name": name, "class": cls, "id": value}
                )
            else:
                self._children.append(
                    {"name": text, "class": "", "id": value}
                )

        if self._children and not self._child_name:
            selected = select.find("option", selected=True)
            if selected:
                text = selected.get_text(strip=True)
                match = re.match(r"^(.+?)\s*\((\w+)\)$", text)
                if match:
                    self._child_name = match.group(1).strip()
                    self._class_name = match.group(2).strip()
                else:
                    self._child_name = text
            elif self._children:
                self._child_name = self._children[0]["name"]
                self._class_name = self._children[0].get("class", "")

    # ------------------------------------------------------------------
    # Schulinformationen
    # ------------------------------------------------------------------

    async def get_school_info(self) -> list[dict[str, Any]]:
        """Fetch /service/schulinformationen."""
        html = await self._fetch_page(PATH_SCHOOL_INFO)
        self._extract_children_from_html(html)
        return self._parse_school_info(html)

    def _parse_school_info(self, html: str) -> list[dict[str, Any]]:
        """Parse school information page (div.row.m_bot layout)."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="asam_content")
        if not content:
            return []

        items: list[dict[str, Any]] = []
        current_section = ""

        for row in content.select("div.row.m_bot"):
            h3 = row.select_one("h3")
            if h3:
                current_section = h3.get_text(strip=True)
                continue

            label_el = row.select_one("div.col-md-4 b")
            if not label_el:
                continue
            label = label_el.get_text(strip=True)
            if not label or label == "\xa0":
                continue

            value_el = row.select_one("div.col-md-6")
            value = ""
            if value_el:
                link = value_el.find("a")
                if link:
                    value = link.get_text(strip=True)
                else:
                    value = value_el.get_text(separator="\n", strip=True)

            entry: dict[str, Any] = {"label": label, "value": value}
            if current_section:
                entry["section"] = current_section
            items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Stundenplan
    # ------------------------------------------------------------------

    async def get_timetable(self) -> list[dict[str, Any]]:
        """Fetch /service/stundenplan."""
        html = await self._fetch_page(PATH_TIMETABLE)
        self._extract_children_from_html(html)
        return self._parse_timetable(html)

    def _parse_timetable(self, html: str) -> list[dict[str, Any]]:
        """Parse timetable page."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="asam_content")
        if not content:
            return []

        result: list[dict[str, Any]] = []

        table = content.select_one("table.table-bordered")
        if table:
            timetable = self._parse_timetable_grid(table)
            if timetable:
                result.append({"type": "timetable", "entries": timetable})

        teachers = self._parse_teachers(content)
        if teachers:
            result.append({"type": "teachers", "entries": teachers})

        for td in content.find_all("td"):
            text = td.get_text(strip=True)
            if text.startswith("Lehrkräfte von "):
                name = text.replace("Lehrkräfte von ", "").strip()
                if name and not self._child_name:
                    self._child_name = name

        return result

    def _parse_timetable_grid(self, table: Tag) -> list[dict[str, Any]]:
        """Parse the timetable table grid."""
        rows = table.find_all("tr")
        if not rows:
            return []

        header_cells = rows[0].find_all(["th", "td"])
        days = [c.get_text(strip=True) for c in header_cells]

        entries: list[dict[str, Any]] = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            period_text = cells[0].get_text(separator="\n", strip=True)
            period_parts = period_text.split("\n")
            period_num = period_parts[0].strip() if period_parts else ""
            period_time = (
                period_parts[1].strip() if len(period_parts) > 1 else ""
            )

            day_entries: dict[str, str] = {}
            for idx, cell in enumerate(cells[1:], start=1):
                day_name = days[idx] if idx < len(days) else f"Tag_{idx}"
                text = cell.get_text(separator="\n", strip=True)
                if text:
                    day_entries[day_name] = text

            if any(day_entries.values()):
                entries.append(
                    {
                        "period": period_num,
                        "time": period_time,
                        **day_entries,
                    }
                )

        return entries

    def _parse_teachers(self, content: Tag) -> list[dict[str, Any]]:
        """Parse the teacher list below the timetable."""
        teachers: list[dict[str, Any]] = []
        current_group = ""

        hr = content.find("hr")
        if not hr:
            return []

        teacher_table = hr.find_next("table")
        if not teacher_table:
            return []

        for row in teacher_table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            if len(cells) == 1 or (
                len(cells) == 2 and cells[0].get("colspan")
            ):
                bold = row.find("b")
                if bold:
                    text = bold.get_text(strip=True)
                    if text and text not in ("", "\xa0"):
                        current_group = text
                continue

            if len(cells) >= 2:
                subject = cells[0].get_text(strip=True)
                teacher = cells[1].get_text(strip=True)
                if subject and teacher:
                    entry: dict[str, Any] = {
                        "subject": subject,
                        "teacher": teacher,
                    }
                    if current_group:
                        entry["group"] = current_group
                    teachers.append(entry)

        return teachers

    # ------------------------------------------------------------------
    # Termine (Schulaufgaben + Allgemein) – shared parser
    # ------------------------------------------------------------------

    async def get_exams(self) -> list[dict[str, Any]]:
        """Fetch /service/termine/liste/schulaufgaben."""
        html = await self._fetch_page(PATH_EXAMS)
        self._extract_children_from_html(html)
        return self._parse_termine(html)

    async def get_appointments(self) -> list[dict[str, Any]]:
        """Fetch /service/termine/liste/allgemein."""
        html = await self._fetch_page(PATH_APPOINTMENTS)
        self._extract_children_from_html(html)
        return self._parse_termine(html)

    def _parse_termine(self, html: str) -> list[dict[str, Any]]:
        """Parse Termine pages (table.table2.termine-table)."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.termine-table")
        if not table:
            content = soup.find("div", id="asam_content")
            if content:
                table = content.find("table")
            if not table:
                return []

        items: list[dict[str, Any]] = []
        current_month = ""
        current_year = ""

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            first_cell = cells[0]
            colspan = first_cell.get("colspan")
            if colspan:
                h4 = first_cell.find("h4")
                if not h4:
                    continue
                if "no_border" in (first_cell.get("class") or []):
                    current_year = h4.get_text(strip=True)
                    continue
                style = first_cell.get("style", "")
                if "#dddddd" in style or first_cell.find("a"):
                    current_month = h4.get_text(strip=True)
                    continue
                continue

            if len(cells) >= 3:
                date = cells[0].get_text(strip=True)
                time = cells[1].get_text(strip=True)
                desc = cells[2].get_text(separator="\n", strip=True)

                entry: dict[str, Any] = {
                    "date": date,
                    "description": desc,
                }
                if time:
                    entry["time"] = time
                if current_month:
                    entry["month"] = current_month
                if current_year:
                    entry["year"] = current_year
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Schwarzes Brett
    # ------------------------------------------------------------------

    async def get_blackboard(self) -> list[dict[str, Any]]:
        """Fetch /aktuelles/schwarzes_brett."""
        html = await self._fetch_page(PATH_BLACKBOARD)
        self._extract_children_from_html(html)
        return self._parse_blackboard(html)

    def _parse_blackboard(self, html: str) -> list[dict[str, Any]]:
        """Parse Schwarzes Brett page."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="asam_content")
        if not content:
            return []

        items: list[dict[str, Any]] = []

        for grid_item in content.select("div.grid-item div.well"):
            entry = self._parse_blackboard_well(grid_item, archived=False)
            if entry:
                items.append(entry)

        for arch_row in content.select("div.row.arch"):
            well = arch_row.select_one("div.well")
            if well:
                entry = self._parse_blackboard_well(well, archived=True)
                if entry:
                    items.append(entry)

        return items

    def _parse_blackboard_well(
        self, well: Tag, archived: bool
    ) -> dict[str, Any] | None:
        """Parse a single blackboard well element."""
        entry: dict[str, Any] = {"archived": archived}

        title_el = well.find("h4")
        if title_el:
            entry["title"] = title_el.get_text(strip=True)

        if archived:
            date_col = well.select_one("div.col-sm-3 p, div.col-md-2 p")
            if date_col:
                entry["date"] = date_col.get_text(strip=True)
            content_rows = well.select("div.row")
            if len(content_rows) >= 2:
                content_col = content_rows[1].select_one(
                    "div.col-sm-9 p, div.col-md-10 p"
                )
                if content_col:
                    entry["content"] = content_col.get_text(
                        separator="\n", strip=True
                    )
        else:
            for p in well.find_all("p"):
                style = p.get("style", "")
                if "font-size" in style and "10px" in style:
                    date_text = p.get_text(strip=True)
                    date_text = re.sub(
                        r"^eingestellt am\s*",
                        "",
                        date_text,
                        flags=re.IGNORECASE,
                    )
                    entry["date"] = date_text
                    break

            for p in well.find_all("p"):
                style = p.get("style", "")
                if "font-size" in style and "10px" in style:
                    continue
                text = p.get_text(strip=True)
                if not text:
                    continue
                link = p.find("a")
                if link and "get_file" in (link.get("href") or ""):
                    entry["has_attachment"] = True
                    attachment_title = link.get("title", "")
                    if attachment_title:
                        entry["attachment"] = attachment_title
                elif text and "content" not in entry:
                    entry["content"] = text

        if entry.get("title") or entry.get("content"):
            return entry
        return None

    # ------------------------------------------------------------------
    # Elternbriefe
    # ------------------------------------------------------------------

    async def get_letters(self) -> list[dict[str, Any]]:
        """Fetch /aktuelles/elternbriefe."""
        html = await self._fetch_page(PATH_LETTERS)
        self._extract_children_from_html(html)
        return self._parse_letters(html)

    def _parse_letters(self, html: str) -> list[dict[str, Any]]:
        """Parse Elternbriefe page (paired tr rows)."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="asam_content")
        if not content:
            return []

        table = content.select_one("table")
        if not table:
            return []

        items: list[dict[str, Any]] = []
        rows = table.find_all("tr")
        i = 0

        while i < len(rows):
            row = rows[i]
            cells = row.find_all("td")

            if len(cells) == 2 and not cells[0].get("colspan"):
                number_text = cells[0].get_text(strip=True)
                status_text = cells[1].get_text(strip=True)

                entry: dict[str, Any] = {"number": number_text}
                entry["acknowledged"] = "noch nicht" not in status_text

                if i + 1 < len(rows):
                    content_row = rows[i + 1]
                    self._parse_letter_content(content_row, entry)
                    i += 2
                else:
                    i += 1

                if entry.get("title"):
                    items.append(entry)
            else:
                i += 1

        return items

    def _parse_letter_content(
        self, row: Tag, entry: dict[str, Any]
    ) -> None:
        """Parse the content row of an Elternbrief."""
        td = row.find("td")
        if not td:
            return

        h4 = td.find("h4")
        if h4:
            entry["title"] = h4.get_text(strip=True)

        link = td.find("a", class_="link_nachrichten")
        span = td.find("span", class_="link_nachrichten")

        if link:
            entry["has_file"] = True
            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = f"{self._base_url}/{href}"
            entry["link"] = href
            link_text = link.get_text(separator="\n", strip=True)
            self._extract_letter_date(link_text, entry)
        elif span:
            entry["has_file"] = False
            span_text = span.get_text(separator="\n", strip=True)
            self._extract_letter_date(span_text, entry)

        class_span = td.find("span", class_="small")
        if class_span:
            class_text = class_span.get_text(strip=True)
            entry["classes"] = class_text

        full_text = td.get_text(separator="\n", strip=True)
        if entry.get("title"):
            full_text = full_text.replace(entry["title"], "", 1)
        if entry.get("classes"):
            full_text = full_text.replace(entry["classes"], "", 1)
        if entry.get("date"):
            full_text = full_text.replace(entry["date"], "", 1)
        full_text = re.sub(r"\(keine Datei[^)]*\)", "", full_text)
        full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
        if full_text:
            entry["body"] = full_text

    def _extract_letter_date(
        self, text: str, entry: dict[str, Any]
    ) -> None:
        """Extract date from letter link/span text."""
        match = re.search(
            r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})", text
        )
        if match:
            entry["date"] = match.group(1).strip()

    # ------------------------------------------------------------------
    # Kommunikation Fachlehrer
    # ------------------------------------------------------------------

    async def get_messages(self) -> list[dict[str, Any]]:
        """Fetch /meldungen/kommunikation_fachlehrer."""
        html = await self._fetch_page(PATH_MESSAGES)
        self._extract_children_from_html(html)
        return self._parse_messages(html)

    def _parse_messages(self, html: str) -> list[dict[str, Any]]:
        """Parse Kommunikation Fachlehrer page."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    entry: dict[str, Any] = {}
                    for idx, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        if text:
                            entry[f"col_{idx}"] = text
                    link = row.find("a", href=True)
                    if link:
                        href = link.get("href", "")
                        if href and not href.startswith("http"):
                            href = f"{self._base_url}/{href}"
                        entry["link"] = href
                    if entry:
                        items.append(entry)

        if items:
            return items

        for card in soup.select(
            ".list-group-item, .card, .panel, .message, .nachricht, "
            ".well, .row.m_bot"
        ):
            entry = {}
            title_el = card.select_one(
                "h4, h5, strong, b, .title, .subject, .betreff"
            )
            if title_el:
                entry["subject"] = title_el.get_text(strip=True)
            date_el = card.select_one("small, .text-muted, .date, time")
            if date_el:
                entry["date"] = date_el.get_text(strip=True)
            link = card.select_one("a[href]")
            if link:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self._base_url}/{href}"
                entry["link"] = href
            if entry.get("subject") or entry.get("date"):
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Umfragen
    # ------------------------------------------------------------------

    async def get_surveys(self) -> list[dict[str, Any]]:
        """Fetch /aktuelles/umfragen."""
        html = await self._fetch_page(PATH_SURVEYS)
        self._extract_children_from_html(html)
        return self._parse_surveys(html)

    def _parse_surveys(self, html: str) -> list[dict[str, Any]]:
        """Parse Umfragen/Abfragen page."""
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="asam_content")
        if not content:
            return []

        items: list[dict[str, Any]] = []

        for row in content.select("div.row.m_bot"):
            entry: dict[str, Any] = {}

            link = row.select_one("a.umf_list, a.link_nachrichten")
            if link:
                entry["title"] = link.get_text(strip=True)
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{self._base_url}/{href}"
                entry["link"] = href

            date_span = row.select_one("div.col-xs-3 span")
            if date_span:
                entry["end_date"] = date_span.get_text(strip=True)

            voted_col = row.select("div.col-xs-3")
            if len(voted_col) >= 2:
                voted_text = voted_col[1].get_text(strip=True)
                entry["voted"] = bool(voted_text)

            if entry.get("title"):
                items.append(entry)

        return items

    # ------------------------------------------------------------------
    # Children detection (from any page's nav)
    # ------------------------------------------------------------------

    async def get_children(self) -> list[dict[str, Any]]:
        """Detect children from the navigation dropdown."""
        html = await self._fetch_page(PATH_TIMETABLE)
        self._extract_children_from_html(html)
        return [
            {"name": c["name"], "class": c.get("class", ""), "id": c["id"]}
            for c in self._children
        ]

    # ------------------------------------------------------------------
    # Aggregated fetch
    # ------------------------------------------------------------------

    async def get_all_data(
        self, enabled_endpoints: set[str] | None = None
    ) -> dict[str, Any]:
        """Fetch all (or selected) endpoints and return combined dict."""
        data: dict[str, Any] = {
            "school_info": [],
            "timetable": [],
            "exams": [],
            "appointments": [],
            "blackboard": [],
            "letters": [],
            "messages": [],
            "surveys": [],
            "child_name": None,
            "class_name": None,
            "children": [],
        }

        fetchers: dict[str, Any] = {
            "school_info": self.get_school_info,
            "timetable": self.get_timetable,
            "exams": self.get_exams,
            "appointments": self.get_appointments,
            "blackboard": self.get_blackboard,
            "letters": self.get_letters,
            "messages": self.get_messages,
            "surveys": self.get_surveys,
        }

        errors: list[str] = []
        for key, fetcher in fetchers.items():
            if enabled_endpoints is not None and key not in enabled_endpoints:
                continue
            try:
                data[key] = await fetcher()
            except ElternPortalAuthError as err:
                _LOGGER.warning("Auth error fetching %s: %s", key, err)
                errors.append(key)
                # If auth fails on first endpoint, don't bother with rest
                if key == "school_info":
                    raise
            except ElternPortalApiError as err:
                _LOGGER.warning("Failed to fetch %s: %s", key, err)
                errors.append(key)

        # If ALL endpoints failed, raise so coordinator can handle it
        if len(errors) == len(fetchers):
            raise ElternPortalApiError(
                f"All {len(errors)} endpoints failed. Connection lost?"
            )

        data["child_name"] = self._child_name
        data["class_name"] = self._class_name
        data["children"] = self._children

        if errors:
            _LOGGER.warning(
                "Partial fetch: %d/%d endpoints failed: %s",
                len(errors),
                len(fetchers),
                ", ".join(errors),
            )

        return data

    # ------------------------------------------------------------------
    # Connection test & cleanup
    # ------------------------------------------------------------------

    async def test_connection(self) -> bool:
        """Test credentials. Raises ElternPortalAuthError or ElternPortalApiError."""
        await self.login()
        return True

    async def close(self) -> None:
        """Close session."""
        if self._session and not self._session.closed:
            try:
                await self._session.get(
                    f"{self._base_url}{ENDPOINT_LOGOUT}"
                )
            except Exception:  # noqa: BLE001
                pass
            await self._session.close()
            self._session = None
            self._logged_in = False