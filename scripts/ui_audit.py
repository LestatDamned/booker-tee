from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

DEFAULT_OUTPUT_DIR = Path("/tmp/booker-ui-audit")
DEFAULT_TIMEOUT_SECONDS = 20
PAGE_TIMEOUT_MS = 8_000

PAGES: tuple[tuple[str, str], ...] = (
    ("/", "dashboard"),
    ("/accounts", "accounts"),
    ("/ledger/manual", "manual-operations"),
    ("/imports", "imports"),
    ("/imports/upload", "imports-upload"),
    ("/rules", "rules"),
    ("/reports", "reports"),
    ("/categories", "categories"),
    ("/properties", "properties"),
    ("/users", "users"),
    ("/workspaces", "workspaces"),
)

VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop", 1440, 1000),
    ("mobile", 390, 844),
)


@dataclass(frozen=True)
class PageAuditResult:
    viewport: str
    path: str
    label: str
    status: int | None
    screenshot: str | None
    horizontal_overflow_px: int
    console_errors: list[str]
    page_errors: list[str]
    failed_requests: list[str]
    overflow_offenders: list[dict[str, Any]]
    error: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and (self.status is None or self.status < 400)
            and self.horizontal_overflow_px <= 1
            and not self.console_errors
            and not self.page_errors
            and not self.failed_requests
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Booker Tee UI with Playwright.")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Use an already running app instead of starting uvicorn.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for screenshots and report JSON.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Server startup timeout in seconds.",
    )
    return parser.parse_args()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(base_url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{base_url}/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, URLError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Server did not become ready at {health_url}: {last_error}")


def start_uvicorn(timeout_seconds: int) -> tuple[str, subprocess.Popen[str]]:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(base_url, timeout_seconds)
    except Exception:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)
        raise RuntimeError(f"Could not start uvicorn:\n{output}") from None
    return base_url, process


def stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def safe_filename(value: str) -> str:
    return value.strip("/").replace("/", "-") or "root"


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def collect_overflow(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const body = document.body;
          const scrollWidth = Math.max(root.scrollWidth, body ? body.scrollWidth : 0);
          const clientWidth = root.clientWidth;
          const offenders = Array.from(document.body.querySelectorAll("*"))
            .map((element) => {
              const rect = element.getBoundingClientRect();
              return {
                tag: element.tagName.toLowerCase(),
                className: element.className ? String(element.className) : "",
                text: (element.innerText || "").trim().slice(0, 80),
                width: Math.round(rect.width),
                right: Math.round(rect.right),
              };
            })
            .filter((item) => (
              item.right > window.innerWidth + 1
              || item.width > window.innerWidth + 1
            ))
            .sort((left, right) => right.right - left.right)
            .slice(0, 8);
          return {
            scrollWidth,
            clientWidth,
            horizontalOverflowPx: Math.max(0, scrollWidth - clientWidth),
            offenders,
          };
        }
        """
    )


def audit_page(
    page: Page,
    *,
    base_url: str,
    path: str,
    label: str,
    viewport_name: str,
    output_dir: Path,
) -> PageAuditResult:
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    page.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "requestfailed",
        lambda request: failed_requests.append(
            f"{request.method} {request.url} {request.failure or ''}".strip()
        ),
    )

    status: int | None = None
    screenshot_path = output_dir / f"{viewport_name}-{safe_filename(label)}.png"
    horizontal_overflow_px = 0
    overflow_offenders: list[dict[str, Any]] = []
    error_text: str | None = None

    try:
        response = page.goto(
            build_url(base_url, path),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT_MS,
        )
        page.wait_for_timeout(300)
        status = response.status if response is not None else None
        overflow = collect_overflow(page)
        horizontal_overflow_px = int(overflow["horizontalOverflowPx"])
        overflow_offenders = list(overflow["offenders"])
        page.screenshot(path=str(screenshot_path), full_page=True)
    except PlaywrightError as exc:
        error_text = str(exc)
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except PlaywrightError:
            screenshot_path = Path("")

    return PageAuditResult(
        viewport=viewport_name,
        path=path,
        label=label,
        status=status,
        screenshot=str(screenshot_path) if screenshot_path else None,
        horizontal_overflow_px=horizontal_overflow_px,
        console_errors=console_errors,
        page_errors=page_errors,
        failed_requests=failed_requests,
        overflow_offenders=overflow_offenders,
        error=error_text,
    )


def run_audit(base_url: str, output_dir: Path) -> list[PageAuditResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[PageAuditResult] = []
    print(f"Auditing {base_url}", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for viewport_name, width, height in VIEWPORTS:
                print(f"Viewport: {viewport_name} ({width}x{height})", flush=True)
                context = browser.new_context(viewport={"width": width, "height": height})
                try:
                    for path, label in PAGES:
                        print(f" - {path}", flush=True)
                        page = context.new_page()
                        try:
                            results.append(
                                audit_page(
                                    page,
                                    base_url=base_url,
                                    path=path,
                                    label=label,
                                    viewport_name=viewport_name,
                                    output_dir=output_dir,
                                )
                            )
                        finally:
                            page.close()
                finally:
                    context.close()
        finally:
            browser.close()
    return results


def write_report(results: list[PageAuditResult], output_dir: Path) -> Path:
    report_path = output_dir / "report.json"
    payload = {
        "passed": all(result.passed for result in results),
        "results": [asdict(result) for result in results],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def print_summary(results: list[PageAuditResult], report_path: Path) -> None:
    failures = [result for result in results if not result.passed]
    print(f"UI audit report: {report_path}")
    print(f"Pages checked: {len(results)}")
    if not failures:
        print("Result: passed")
        return

    print(f"Result: failed ({len(failures)} issue groups)")
    for result in failures:
        parts = [f"{result.viewport}:{result.path}"]
        if result.status is not None and result.status >= 400:
            parts.append(f"HTTP {result.status}")
        if result.horizontal_overflow_px > 1:
            parts.append(f"overflow {result.horizontal_overflow_px}px")
        if result.console_errors:
            parts.append(f"console errors {len(result.console_errors)}")
        if result.page_errors:
            parts.append(f"page errors {len(result.page_errors)}")
        if result.failed_requests:
            parts.append(f"failed requests {len(result.failed_requests)}")
        if result.error:
            parts.append("navigation error")
        print(" - " + "; ".join(parts))


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    server_process: subprocess.Popen[str] | None = None
    base_url = args.base_url
    try:
        if base_url is None:
            base_url, server_process = start_uvicorn(args.timeout)
        results = run_audit(base_url, output_dir)
        report_path = write_report(results, output_dir)
        print_summary(results, report_path)
        return 0 if all(result.passed for result in results) else 1
    finally:
        stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
