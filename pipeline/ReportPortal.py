"""Step 1 of the pipeline: connect to the report portal, list the reports, download them."""
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .Settings import Settings

# Pulls the file name out of a header like: Content-Disposition: attachment; filename="x.xlsx"
_FILENAME_RE = re.compile(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", re.IGNORECASE)
# Characters Windows does not allow in file names
_BAD_CHARS_RE = re.compile(r'[<>:"/\\|?*]')


class ReportPortal:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = None
        self.connect_to_portal()

    def connect_to_portal(self) -> None:
        """One HTTP session, reused for every request in a check (keeps the connection and login)."""
        self.session = requests.Session()
        if self.settings.auth_mode == "windows":
            # Logs in as the current Windows user, like the browser does. Windows-only package.
            from requests_negotiate_sspi import HttpNegotiateAuth
            self.session.auth = HttpNegotiateAuth()

    def find_reports(self) -> dict[str, str]:
        """Return {download_url: link_text} for every report link on the portal page."""
        resp = self.session.get(self.settings.portal_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        reports = {}
        for link in soup.select(self.settings.link_selector):
            href = link.get("href")
            if href:
                reports[urljoin(resp.url, href)] = link.get_text(strip=True)
        return reports

    @staticmethod
    def pick_newest_report(urls: list[str]) -> str:
        """Pick the newest report. Each report URL has a fileid that grows with every new report,
        so the highest fileid is the newest. Without a fileid, the first link on the page wins
        (the portal lists the newest report first)."""
        def file_id(url: str) -> int:
            ids = parse_qs(urlparse(url).query).get("fileid", [""])
            return int(ids[0]) if ids[0].isdigit() else -1
        return max(urls, key=file_id)

    def download_report(self, url: str, name_hint: str = "") -> Path:
        """Download one report into the download folder and return the saved file path."""
        download_dir = self.settings.download_dir
        download_dir.mkdir(parents=True, exist_ok=True)
        with self.session.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            if "text/html" in resp.headers.get("Content-Type", ""):
                raise RuntimeError("Got an HTML page instead of a file - probably not logged in")

            target = download_dir / self._get_file_name(resp, url, name_hint)
            if target.exists():  # never overwrite an existing report
                target = target.with_name(f"{target.stem}_{datetime.now():%Y%m%d_%H%M%S}{target.suffix}")

            # Write to .part first and rename at the end, so step 2 never sees a half-written file.
            part = target.with_name(target.name + ".part")
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    f.write(chunk)
            part.replace(target)
        return target

    @staticmethod
    def _get_file_name(resp: requests.Response, url: str, name_hint: str) -> str:
        """Prefer the name the server sends, then the link text, then the URL path."""
        match = _FILENAME_RE.search(resp.headers.get("Content-Disposition", ""))
        if match:
            name = unquote(match.group(1))
        else:
            name = name_hint or Path(unquote(urlparse(url).path)).name
        return _BAD_CHARS_RE.sub("_", name).strip() or "report"
