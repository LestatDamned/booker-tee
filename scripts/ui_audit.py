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

from openpyxl import Workbook
from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

DEFAULT_OUTPUT_DIR = Path("/tmp/booker-ui-audit")
DEFAULT_AUTH_OUTPUT_DIR = Path("/tmp/booker-ui-audit-auth")
DEFAULT_REALISTIC_OUTPUT_DIR = Path("/tmp/booker-ui-audit-realistic")
DEFAULT_REVIEW_OUTPUT_DIR = Path("/tmp/booker-ui-audit-review")
DEFAULT_BUTTON_OUTPUT_DIR = Path("/tmp/booker-ui-audit-buttons")
DEFAULT_DESIGN_OUTPUT_DIR = Path("/tmp/booker-ui-audit-design")
DEFAULT_TIMEOUT_SECONDS = 20
PAGE_TIMEOUT_MS = 8_000
DEFAULT_AUTH_PASSWORD = "booker-ui-audit-password"
MAX_CLICK_TARGETS_PER_PAGE = 60

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

AUTHENTICATED_PAGES: tuple[tuple[str, str], ...] = (
    ("/dashboard", "dashboard"),
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
    ux_assertion_errors: list[str]
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
            and not self.ux_assertion_errors
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
    parser.add_argument(
        "--authenticated",
        action="store_true",
        help="Register a temporary user in the browser and audit authenticated pages.",
    )
    parser.add_argument(
        "--auth-email",
        default=None,
        help="Email for authenticated audit. Defaults to a unique @example.test address.",
    )
    parser.add_argument(
        "--auth-password",
        default=DEFAULT_AUTH_PASSWORD,
        help="Password for the authenticated audit user.",
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "empty",
            "realistic",
            "review_interactions",
            "button_audit",
            "design_audit",
        ),
        default="empty",
        help="Data scenario to prepare before auditing authenticated pages.",
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


def build_auth_email(viewport_name: str, provided_email: str | None) -> str:
    if provided_email is not None:
        return provided_email
    return f"ui-audit-{viewport_name}-{time.time_ns()}@example.test"


def authenticate_context(
    context: BrowserContext,
    *,
    base_url: str,
    viewport_name: str,
    email: str | None,
    password: str,
) -> None:
    page = context.new_page()
    auth_email = build_auth_email(viewport_name, email)
    try:
        try_register(page, base_url=base_url, email=auth_email, password=password)
    except PlaywrightError as exc:
        if email is not None:
            try:
                try_login(page, base_url=base_url, email=auth_email, password=password)
                return
            except PlaywrightError:
                pass
        body_text = page.locator("body").inner_text(timeout=1_000)
        raise RuntimeError(f"Could not authenticate UI audit user: {body_text}") from exc
    finally:
        page.close()


def try_register(page: Page, *, base_url: str, email: str, password: str) -> None:
    response = page.goto(
        build_url(base_url, "/signup"),
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT_MS,
    )
    if response is not None and response.status >= 400:
        raise RuntimeError(f"Could not open signup page: HTTP {response.status}")

    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="name"]').fill("UI Audit")
    page.locator('input[name="password"]').fill(password)
    page.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    page.wait_for_url("**/workspaces", timeout=PAGE_TIMEOUT_MS)


def try_login(page: Page, *, base_url: str, email: str, password: str) -> None:
    response = page.goto(
        build_url(base_url, "/login"),
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT_MS,
    )
    if response is not None and response.status >= 400:
        raise RuntimeError(f"Could not open login page: HTTP {response.status}")

    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    page.wait_for_url("**/workspaces", timeout=PAGE_TIMEOUT_MS)


def prepare_realistic_scenario(
    context: BrowserContext,
    *,
    base_url: str,
    output_dir: Path,
    viewport_name: str,
) -> dict[str, str]:
    scenario_id = f"{viewport_name}-{time.time_ns()}"
    account_name = f"UI Audit Cash {scenario_id}"
    document_name = f"ui-audit-statement-{scenario_id}.xlsx"
    workbook_path = output_dir / document_name
    create_statement_fixture(workbook_path)

    page = context.new_page()
    try:
        page.goto(build_url(base_url, "/accounts"), wait_until="domcontentloaded")
        page.locator('form#new-account input[name="name"]').fill(account_name)
        page.locator('form#new-account select[name="account_type"]').select_option("cash")
        page.locator('form#new-account input[name="currency"]').fill("RUB")
        page.locator('form#new-account input[name="initial_balance"]').fill("10000.00")
        page.locator('form#new-account button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text(account_name, exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)

        page.goto(build_url(base_url, "/imports/upload"), wait_until="domcontentloaded")
        page.locator('input[name="statement_pdf"]').set_input_files(str(workbook_path))
        page.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.wait_for_url("**/imports/documents/**", timeout=PAGE_TIMEOUT_MS)
    finally:
        page.close()

    return {
        "account_name": account_name,
        "document_name": document_name,
    }


def prepare_review_interaction_scenario(
    context: BrowserContext,
    *,
    base_url: str,
    output_dir: Path,
    viewport_name: str,
) -> dict[str, str]:
    scenario_state = prepare_realistic_scenario(
        context,
        base_url=base_url,
        output_dir=output_dir,
        viewport_name=viewport_name,
    )
    page = context.new_page()
    try:
        detail_url = page.url
        if "/imports/documents/" not in detail_url:
            page.goto(build_url(base_url, "/imports"), wait_until="domcontentloaded")
            document_card = page.locator(".entity-card").filter(
                has_text=scenario_state["document_name"]
            )
            document_card.wait_for(timeout=PAGE_TIMEOUT_MS)
            document_card.locator('a[href*="/imports/documents/"]').filter(
                has_text="детали"
            ).first.click()
            page.wait_for_url("**/imports/documents/**", timeout=PAGE_TIMEOUT_MS)
            detail_url = page.url

        mapping_url = f"{detail_url.rstrip('/')}/mapping"
        page.goto(mapping_url, wait_until="domcontentloaded")
        page.locator("#mapping-form").wait_for(timeout=PAGE_TIMEOUT_MS)
        page.locator('select[name="operation_date_column"]').select_option("0")
        page.locator('select[name="description_column"]').select_option("1")
        page.locator('select[name="amount_column"]').select_option("2")
        page.locator('select[name="currency_column"]').select_option("3")
        page.locator('input[name="first_data_row"]').fill("1")
        page.locator('button[type="submit"]').filter(has_text="показать предпросмотр").click()
        page.get_by_text("Предпросмотр транзакций").wait_for(timeout=PAGE_TIMEOUT_MS)
        page.locator('button[formaction$="/mapping/import"]').click()
        page.wait_for_url("**/imports/documents/**/review", timeout=PAGE_TIMEOUT_MS)
        scenario_state["review_path"] = page.url.replace(base_url.rstrip("/"), "")
    finally:
        page.close()

    return scenario_state


def create_statement_fixture(path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Statement"
    worksheet.append(["Дата", "Описание", "Сумма", "Валюта"])
    worksheet.append(["2026-06-01", "OZON Маркетплейс", "-1234.56", "RUB"])
    worksheet.append(["2026-06-02", "Зарплата", "50000.00", "RUB"])
    worksheet.append(["2026-06-03", "Перевод между счетами", "-10000.00", "RUB"])
    workbook.save(path)
    workbook.close()


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


def collect_ux_assertions(
    page: Page,
    *,
    base_url: str,
    path: str,
    scenario: str,
    scenario_state: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    if path in {"/", "/dashboard"}:
        errors.extend(assert_dashboard_ui(page))

    if scenario == "realistic" and path == "/dashboard":
        body_text = page.locator("body").inner_text(timeout=PAGE_TIMEOUT_MS)
        account_name = scenario_state.get("account_name")
        document_name = scenario_state.get("document_name")
        if account_name and account_name not in body_text:
            errors.append(f"dashboard does not show seeded account {account_name!r}")
        if document_name and document_name not in body_text:
            errors.append(f"dashboard does not show seeded document {document_name!r}")

    if scenario == "review_interactions" and path == scenario_state.get("review_path"):
        errors.extend(assert_review_interactions(page, scenario_state=scenario_state))

    if scenario == "button_audit":
        errors.extend(assert_safe_click_interactions(page, base_url=base_url))

    if scenario == "design_audit":
        errors.extend(assert_design_quality(page, path=path))

    return errors


def assert_design_quality(page: Page, *, path: str) -> list[str]:
    state = page.evaluate(
        """
        () => {
          const visible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            const closedDetails = element.closest('details:not([open])');
            if (closedDetails && element !== closedDetails.querySelector(':scope > summary')) {
              return false;
            }
            return rect.width > 0
              && rect.height > 0
              && style.display !== 'none'
              && style.visibility !== 'hidden';
          };
          const textFor = (element) => (
            element.innerText || element.getAttribute('aria-label') || ''
          ).trim().replace(/\\s+/g, ' ');
          const borderWidth = (style) => (
            parseFloat(style.borderTopWidth)
            + parseFloat(style.borderRightWidth)
            + parseFloat(style.borderBottomWidth)
            + parseFloat(style.borderLeftWidth)
          );
          const isTransparent = (color) => (
            !color || color === 'transparent' || color === 'rgba(0, 0, 0, 0)'
          );
          const controlSelector = [
            'a.button',
            'button:not([type="hidden"])',
            'details.action-details > summary',
            'details.action-accordion > summary'
          ].join(',');
          const visibleMainControls = Array.from(
            document.querySelectorAll(`main ${controlSelector}`)
          ).filter(visible);
          const pageControls = visibleMainControls
            .filter((element) => !element.closest('.site-header'))
            .map((element) => textFor(element));

          const blockIssues = Array.from(
            document.querySelectorAll(
              '.entity-card, .review-item, .raw-transaction-card, .parse-attempt-card'
            )
          ).filter(visible).map((block, index) => {
            const controls = Array.from(block.querySelectorAll(controlSelector))
              .filter(visible)
              .filter((element) => !element.closest('.technical-details'))
              .map((element) => textFor(element))
              .filter(Boolean);
            const primaryActions = Array.from(
              block.querySelectorAll('.primary-action, .button.primary-action')
            ).filter(visible).map((element) => textFor(element)).filter(Boolean);
            return {
              index: index + 1,
              label: textFor(block).slice(0, 80),
              controls,
              primaryActions,
            };
          });

          const technicalSummaries = Array.from(
            document.querySelectorAll('details.technical-details > summary')
          ).filter(visible).map((summary) => {
            const rect = summary.getBoundingClientRect();
            const style = getComputedStyle(summary);
            return {
              text: textFor(summary),
              height: Math.round(rect.height),
              width: Math.round(rect.width),
              borderWidth: borderWidth(style),
              backgroundColor: style.backgroundColor,
              insideDenseBlock: Boolean(
                summary.closest('.entity-card, .review-item, .raw-transaction-card')
              ),
            };
          });

          const badgeMetrics = Array.from(document.querySelectorAll('.badge'))
            .filter(visible)
            .map((badge) => {
              const rect = badge.getBoundingClientRect();
              return {
                text: textFor(badge),
                height: Math.round(rect.height),
                width: Math.round(rect.width),
              };
            });

          const radiusOffenders = Array.from(document.querySelectorAll('*'))
            .filter(visible)
            .map((element) => {
              const style = getComputedStyle(element);
              const radii = [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
              ].map((value) => parseFloat(value) || 0);
              return {
                tag: element.tagName.toLowerCase(),
                className: String(element.className || ''),
                text: textFor(element).slice(0, 60),
                maxRadius: Math.max(...radii),
              };
            })
            .filter((item) => item.maxRadius > 0.5)
            .slice(0, 6);

          const visibleDebugBlocks = Array.from(document.querySelectorAll('pre'))
            .filter(visible)
            .map((element) => textFor(element).slice(0, 60));

          const webOneControlLabels = visibleMainControls
            .map((element) => {
              const rect = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                text: textFor(element),
                height: Math.round(rect.height),
                borderWidth: borderWidth(style),
                backgroundColor: style.backgroundColor,
              };
            })
            .filter((item) => (
              /технические детали/i.test(item.text)
              && (
                item.height >= 34
                || item.borderWidth > 0
                || !isTransparent(item.backgroundColor)
              )
            ))
            .map((item) => item.text);

          return {
            pageControls,
            blockIssues,
            technicalSummaries,
            badgeMetrics,
            radiusOffenders,
            visibleDebugBlocks,
            webOneControlLabels,
            viewportWidth: window.innerWidth,
          };
        }
        """
    )
    errors: list[str] = []
    viewport_width = int(state.get("viewportWidth") or 0)
    page_controls = list(state.get("pageControls") or [])
    control_limit = 24 if viewport_width < 720 else 34
    if len(page_controls) > control_limit:
        errors.append(
            "designer audit: too many visible page actions "
            f"({len(page_controls)} > {control_limit}); page feels like a control board"
        )

    for block in list(state.get("blockIssues") or []):
        controls = list(block.get("controls") or [])
        primary_actions = list(block.get("primaryActions") or [])
        label = str(block.get("label") or f"block {block.get('index')}")
        block_limit = 4 if viewport_width < 720 else 5
        if len(controls) > block_limit:
            errors.append(
                "designer audit: action noise in block "
                f"{block.get('index')} ({len(controls)} controls): "
                f"{label!r}"
            )
        if len(primary_actions) > 1:
            errors.append(
                "designer audit: more than one primary action in block "
                f"{block.get('index')}: {primary_actions}"
            )

    technical_summaries = list(state.get("technicalSummaries") or [])
    noisy_technical = [
        item
        for item in technical_summaries
        if (
            str(item.get("text") or "").casefold().startswith("технические детали")
            and item.get("insideDenseBlock")
        )
        or float(item.get("height") or 0) >= 34
        or float(item.get("borderWidth") or 0) > 0
    ]
    if noisy_technical:
        examples = ", ".join(str(item.get("text") or "") for item in noisy_technical[:3])
        errors.append(
            "designer audit: technical details compete with user actions "
            f"({len(noisy_technical)} visible triggers; examples: {examples})"
        )

    web_one_controls = list(state.get("webOneControlLabels") or [])
    if web_one_controls:
        errors.append(
            "designer audit: Web 1.0-like technical controls are visually prominent: "
            + ", ".join(str(label) for label in web_one_controls[:4])
        )

    badge_metrics = list(state.get("badgeMetrics") or [])
    if len(badge_metrics) >= 2:
        heights = [int(item.get("height") or 0) for item in badge_metrics]
        min_height = min(heights)
        max_height = max(heights)
        if max_height - min_height > 4:
            tall_badges = [
                str(item.get("text") or "")
                for item in badge_metrics
                if int(item.get("height") or 0) == max_height
            ][:3]
            errors.append(
                "designer audit: inconsistent badge heights "
                f"({min_height}px..{max_height}px; examples: {tall_badges})"
            )

    radius_offenders = list(state.get("radiusOffenders") or [])
    if radius_offenders:
        examples = ", ".join(
            f"{item.get('tag')}.{item.get('className')}" for item in radius_offenders[:3]
        )
        errors.append(f"designer audit: rounded corners found despite design rule: {examples}")

    visible_debug_blocks = list(state.get("visibleDebugBlocks") or [])
    if visible_debug_blocks:
        errors.append(
            "designer audit: raw debug/code blocks are visible by default "
            f"({len(visible_debug_blocks)} blocks); hide them behind debug details"
        )

    if path in {"/imports", "/accounts", "/categories", "/properties", "/rules"}:
        long_technical_labels = [
            str(item.get("text") or "")
            for item in technical_summaries
            if str(item.get("text") or "").casefold().startswith("технические детали")
        ]
        if long_technical_labels:
            errors.append(
                "designer audit: list pages should use short quiet technical triggers "
                f"instead of {long_technical_labels[:3]}"
            )

    return errors


def assert_safe_click_interactions(page: Page, *, base_url: str) -> list[str]:
    errors: list[str] = []
    original_url = page.url
    errors.extend(click_visible_summaries(page))
    errors.extend(click_safe_type_buttons(page))
    errors.extend(click_safe_links(page, base_url=base_url, original_url=original_url))
    return errors


def click_visible_summaries(page: Page) -> list[str]:
    errors: list[str] = []
    summaries = page.locator("summary:visible")
    count = min(summaries.count(), MAX_CLICK_TARGETS_PER_PAGE)
    for index in range(count):
        summary = summaries.nth(index)
        label = interaction_label(summary, fallback=f"summary #{index + 1}")
        try:
            summary.click(timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(100)
        except PlaywrightError as exc:
            errors.append(f"summary click failed ({label}): {short_error(exc)}")
    return errors


def click_safe_type_buttons(page: Page) -> list[str]:
    errors: list[str] = []
    buttons = page.locator('button[type="button"]:visible')
    count = min(buttons.count(), MAX_CLICK_TARGETS_PER_PAGE)
    for index in range(count):
        button = buttons.nth(index)
        label = interaction_label(button, fallback=f"button #{index + 1}")
        if should_skip_interaction(label):
            continue
        try:
            button.click(timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(150)
            dismiss_open_dialogs(page)
        except PlaywrightError as exc:
            errors.append(f"button click failed ({label}): {short_error(exc)}")
    return errors


def click_safe_links(page: Page, *, base_url: str, original_url: str) -> list[str]:
    errors: list[str] = []
    link_targets = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]'))
          .filter((element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0
              && rect.height > 0
              && style.visibility !== 'hidden'
              && style.display !== 'none';
          })
          .map((element) => ({
            href: element.href,
            rawHref: element.getAttribute('href') || '',
            text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
            target: element.getAttribute('target') || '',
          }))
          .slice(0, 80)
        """
    )
    unique_targets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target in link_targets:
        href = str(target.get("href") or "")
        text = str(target.get("text") or "")
        key = (href, text)
        if key not in seen:
            seen.add(key)
            unique_targets.append(
                {
                    "href": href,
                    "rawHref": str(target.get("rawHref") or ""),
                    "text": text,
                    "target": str(target.get("target") or ""),
                }
            )

    for target in unique_targets[:MAX_CLICK_TARGETS_PER_PAGE]:
        href = target["href"]
        raw_href = target["rawHref"]
        label = target["text"] or raw_href or href
        if should_skip_link(
            href=href,
            raw_href=raw_href,
            label=label,
            base_url=base_url,
            target=target["target"],
        ):
            continue
        try:
            selector = f'a[href="{css_string_escape(raw_href)}"]'
            link = page.locator(selector).filter(has_text=target["text"]).first
            if link.count() == 0:
                link = page.locator(selector).first
            if link.count() == 0:
                errors.append(f"link disappeared before click ({label})")
                continue
            navigation_response = None
            try:
                with page.expect_navigation(
                    wait_until="domcontentloaded",
                    timeout=2_000,
                ) as navigation_info:
                    link.click(timeout=PAGE_TIMEOUT_MS)
                navigation_response = navigation_info.value
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(150)
            if navigation_response is not None and navigation_response.status >= 400:
                errors.append(
                    f"link returned HTTP {navigation_response.status} ({label} -> {href})"
                )
            body_text = page.locator("body").inner_text(timeout=PAGE_TIMEOUT_MS)
            if "Internal Server Error" in body_text or '"detail":"Not Found"' in body_text:
                errors.append(f"link opened error page ({label} -> {href})")
        except PlaywrightError as exc:
            errors.append(f"link click failed ({label} -> {href}): {short_error(exc)}")
        finally:
            if page.url != original_url:
                try:
                    page.goto(original_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    page.wait_for_timeout(100)
                except PlaywrightError as exc:
                    errors.append(
                        f"could not return to source page after {label}: {short_error(exc)}"
                    )
                    break
    return errors


def dismiss_open_dialogs(page: Page) -> None:
    cancel_buttons = page.locator('dialog[open] button[type="button"]:visible').filter(
        has_text="Отмена"
    )
    if cancel_buttons.count():
        cancel_buttons.first.click(timeout=PAGE_TIMEOUT_MS)
        page.wait_for_timeout(100)
        return
    if page.locator("dialog[open]").count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)


def interaction_label(locator: Any, *, fallback: str) -> str:
    try:
        text = locator.inner_text(timeout=1_000).strip()
    except PlaywrightError:
        text = ""
    return " ".join(text.split()) or fallback


def should_skip_interaction(label: str) -> bool:
    normalized = label.casefold()
    skip_markers = (
        "удалить",
        "игнорировать",
        "архив",
        "выйти",
        "отменить проведение",
        "перепарсить",
    )
    return any(marker in normalized for marker in skip_markers)


def should_skip_link(
    *,
    href: str,
    raw_href: str,
    label: str,
    base_url: str,
    target: str,
) -> bool:
    if not href or not raw_href or raw_href.startswith("#") or target == "_blank":
        return True
    if not href.startswith(base_url.rstrip("/")):
        return True
    if should_skip_interaction(label):
        return True
    return False


def css_string_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def short_error(exc: Exception) -> str:
    return str(exc).splitlines()[0][:220]


def assert_dashboard_ui(page: Page) -> list[str]:
    state = page.evaluate(
        """
        () => {
          const cssLink = document.querySelector('link[rel="stylesheet"][href*="app.css"]');
          const list = document.querySelector(".onboarding-list");
          const item = document.querySelector(".onboarding-item");
          const checklist = document.querySelector(".onboarding-checklist");
          const checklistRect = checklist ? checklist.getBoundingClientRect() : null;
          const dashboard = document.querySelector(".dashboard-grid");
          const dashboardRect = dashboard ? dashboard.getBoundingClientRect() : null;
          return {
            cssHref: cssLink ? cssLink.getAttribute("href") : "",
            hasChecklist: Boolean(checklist),
            listDisplay: list ? getComputedStyle(list).display : null,
            listStyleType: list ? getComputedStyle(list).listStyleType : null,
            itemDisplay: item ? getComputedStyle(item).display : null,
            checklistWidth: checklistRect ? Math.round(checklistRect.width) : null,
            dashboardWidth: dashboardRect ? Math.round(dashboardRect.width) : null,
            onboardingIndexCount: document.querySelectorAll(".onboarding-index").length,
            onboardingItemCount: document.querySelectorAll(".onboarding-item").length,
          };
        }
        """
    )
    errors: list[str] = []
    css_href = str(state.get("cssHref") or "")
    if "app.css?v=" not in css_href:
        errors.append("dashboard stylesheet is not cache-busted")
    if "20260618-ui5" in css_href:
        errors.append("dashboard stylesheet uses stale manual cache key")

    if state.get("hasChecklist"):
        if state.get("listStyleType") != "none":
            errors.append(
                f"onboarding list marker is {state.get('listStyleType')!r}, expected 'none'"
            )
        if state.get("listDisplay") != "grid":
            errors.append(
                f"onboarding list display is {state.get('listDisplay')!r}, expected 'grid'"
            )
        if state.get("itemDisplay") != "grid":
            errors.append(
                f"onboarding item display is {state.get('itemDisplay')!r}, expected 'grid'"
            )
        if state.get("onboardingIndexCount") != state.get("onboardingItemCount"):
            errors.append("onboarding index count does not match item count")

        checklist_width = state.get("checklistWidth")
        dashboard_width = state.get("dashboardWidth")
        if (
            isinstance(checklist_width, int)
            and isinstance(dashboard_width, int)
            and checklist_width < dashboard_width * 0.8
        ):
            errors.append("onboarding checklist is too narrow for the dashboard grid")

    return errors


def assert_review_interactions(page: Page, *, scenario_state: dict[str, str]) -> list[str]:
    errors: list[str] = []
    page.locator(".review-item").first.wait_for(timeout=PAGE_TIMEOUT_MS)
    row = page.locator(".review-item").first
    row_id = row.get_attribute("id") or ""
    if not row_id:
        errors.append("first review row has no stable id")
        return errors

    page.evaluate(
        """
        (rowId) => {
          const row = document.getElementById(rowId);
          if (row) {
            row.scrollIntoView({ block: "center" });
          }
        }
        """,
        row_id,
    )
    page.wait_for_timeout(100)
    before_top = locator_top(row)

    category_details = row.locator("details.action-accordion").filter(has_text="Категория").first
    category_details.locator("summary").click()
    if category_details.get_attribute("open") is None:
        errors.append("category accordion did not open")

    row.locator(".inline-create-button").first.click()
    dialog = row.locator("dialog.review-dialog")
    try:
        dialog.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError:
        errors.append("category dialog did not become visible")
    else:
        open_state = dialog.evaluate("(element) => element.open")
        if not open_state:
            errors.append("category dialog is visible but not open")
        box = dialog.bounding_box()
        if box:
            viewport = page.viewport_size or {"width": 0, "height": 0}
            center_x = box["x"] + box["width"] / 2
            center_y = box["y"] + box["height"] / 2
            if abs(center_x - viewport["width"] / 2) > max(120, viewport["width"] * 0.25):
                errors.append("category dialog is not horizontally centered enough")
            if abs(center_y - viewport["height"] / 2) > max(140, viewport["height"] * 0.3):
                errors.append("category dialog is not vertically centered enough")

        dialog.locator('button[type="button"]').filter(has_text="Отмена").click()
        page.wait_for_timeout(100)
        if dialog.evaluate("(element) => element.open"):
            errors.append("category dialog did not close after cancel")

    category_name = f"UI Audit Category {time.time_ns()}"
    scenario_state["category_name"] = category_name
    row.locator(".inline-create-button").first.click()
    dialog.locator('input[name="name"]').fill(category_name)
    with page.expect_response(lambda response: response.request.method == "POST"):
        dialog.locator('button[type="submit"]').click()
    page.wait_for_timeout(500)
    refreshed_row = page.locator(f"#{row_id}")
    if refreshed_row.count() == 0:
        errors.append("review row disappeared after category creation")
        return errors
    if refreshed_row.locator("details.action-accordion[open]").count() == 0:
        errors.append("category accordion did not stay open after category creation")
    if refreshed_row.locator(f'text="{category_name}"').count() == 0:
        errors.append("created category is not visible in refreshed review row")

    confirm_button = (
        refreshed_row.locator('button[type="submit"]').filter(has_text="Подтвердить").first
    )
    if confirm_button.count() == 0:
        confirm_button = (
            refreshed_row.locator('button[type="submit"]')
            .filter(has_text="Сохранить и подтвердить")
            .first
        )
    if confirm_button.count() == 0:
        errors.append("confirm button was not found in review row")
        return errors

    before_top = locator_top(refreshed_row) or before_top
    with page.expect_response(lambda response: response.request.method == "POST"):
        confirm_button.click()
    page.wait_for_timeout(700)
    confirmed_row = page.locator(f"#{row_id}")
    if confirmed_row.count() == 0:
        errors.append("review row disappeared after HTMX confirm")
        return errors
    after_top = locator_top(confirmed_row)
    if isinstance(before_top, (int, float)) and isinstance(after_top, (int, float)):
        if abs(after_top - before_top) > 160:
            errors.append(
                f"review row jumped {abs(after_top - before_top):.0f}px after HTMX confirm"
            )
    if confirmed_row.locator(".operation-ref").count() == 0:
        errors.append("confirmed review row does not show operation reference")
    next_step_text = page.locator("#review-next-step").inner_text(timeout=PAGE_TIMEOUT_MS)
    if "Осталось обработать 2 из 3 строк." not in next_step_text:
        errors.append("review progress did not update after HTMX confirm")

    return errors


def locator_top(locator: Any) -> float | None:
    box = locator.bounding_box()
    if box is None:
        return None
    return float(box["y"])


def audit_page(
    page: Page,
    *,
    base_url: str,
    path: str,
    label: str,
    viewport_name: str,
    output_dir: Path,
    scenario: str,
    scenario_state: dict[str, str],
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
    ux_assertion_errors: list[str] = []
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
        ux_assertion_errors = collect_ux_assertions(
            page,
            base_url=base_url,
            path=path,
            scenario=scenario,
            scenario_state=scenario_state,
        )
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
        ux_assertion_errors=ux_assertion_errors,
        overflow_offenders=overflow_offenders,
        error=error_text,
    )


def run_audit(
    base_url: str,
    output_dir: Path,
    *,
    authenticated: bool,
    auth_email: str | None,
    auth_password: str,
    scenario: str,
) -> list[PageAuditResult]:
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
                    if authenticated:
                        authenticate_context(
                            context,
                            base_url=base_url,
                            viewport_name=viewport_name,
                            email=auth_email,
                            password=auth_password,
                        )

                    scenario_state: dict[str, str] = {}
                    if scenario == "realistic":
                        scenario_state = prepare_realistic_scenario(
                            context,
                            base_url=base_url,
                            output_dir=output_dir,
                            viewport_name=viewport_name,
                        )
                    elif scenario in {"review_interactions", "button_audit", "design_audit"}:
                        scenario_state = prepare_review_interaction_scenario(
                            context,
                            base_url=base_url,
                            output_dir=output_dir,
                            viewport_name=viewport_name,
                        )

                    pages = AUTHENTICATED_PAGES if authenticated else PAGES
                    if scenario in {
                        "review_interactions",
                        "button_audit",
                        "design_audit",
                    } and scenario_state.get("review_path"):
                        pages = (*pages, (scenario_state["review_path"], "review-interactions"))
                    for path, label in pages:
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
                                    scenario=scenario,
                                    scenario_state=scenario_state,
                                )
                            )
                        finally:
                            page.close()
                finally:
                    context.close()
        finally:
            browser.close()
    return results


def write_report(results: list[PageAuditResult], output_dir: Path, *, scenario: str) -> Path:
    report_path = output_dir / "report.json"
    payload = {
        "passed": all(result.passed for result in results),
        "scenario": scenario,
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
        if result.ux_assertion_errors:
            parts.append(f"UX assertions {len(result.ux_assertion_errors)}")
        if result.error:
            parts.append("navigation error")
        print(" - " + "; ".join(parts))
        for assertion_error in result.ux_assertion_errors:
            print(f"   * {assertion_error}")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    authenticated = bool(args.authenticated or args.scenario != "empty")
    if args.scenario == "review_interactions" and args.output_dir == str(DEFAULT_OUTPUT_DIR):
        output_dir = DEFAULT_REVIEW_OUTPUT_DIR
    elif args.scenario == "button_audit" and args.output_dir == str(DEFAULT_OUTPUT_DIR):
        output_dir = DEFAULT_BUTTON_OUTPUT_DIR
    elif args.scenario == "design_audit" and args.output_dir == str(DEFAULT_OUTPUT_DIR):
        output_dir = DEFAULT_DESIGN_OUTPUT_DIR
    elif args.scenario == "realistic" and args.output_dir == str(DEFAULT_OUTPUT_DIR):
        output_dir = DEFAULT_REALISTIC_OUTPUT_DIR
    elif authenticated and args.output_dir == str(DEFAULT_OUTPUT_DIR):
        output_dir = DEFAULT_AUTH_OUTPUT_DIR
    server_process: subprocess.Popen[str] | None = None
    base_url = args.base_url
    try:
        if base_url is None:
            base_url, server_process = start_uvicorn(args.timeout)
        results = run_audit(
            base_url,
            output_dir,
            authenticated=authenticated,
            auth_email=args.auth_email,
            auth_password=args.auth_password,
            scenario=args.scenario,
        )
        report_path = write_report(results, output_dir, scenario=args.scenario)
        print_summary(results, report_path)
        return 0 if all(result.passed for result in results) else 1
    finally:
        stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
