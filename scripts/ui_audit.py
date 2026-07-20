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
from playwright.sync_api import BrowserContext, Locator, Page, sync_playwright
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
    ("/_next/foundation", "frontend-next-foundation"),
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
    ("/_next/foundation", "frontend-next-foundation"),
    ("/_next/ledger/manual", "frontend-next-manual-ledger"),
    ("/app/ledger/manual", "react-manual-ledger"),
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
    ("tablet", 920, 900),
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
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Audit only this path. Repeat the option to select several paths.",
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


def open_details_if_closed(page: Page, selector: str) -> None:
    details = page.locator(selector).first
    if details.count() == 0:
        return
    if details.get_attribute("open") is None:
        details.locator("summary").first.click(timeout=PAGE_TIMEOUT_MS)


def prepare_realistic_scenario(
    context: BrowserContext,
    *,
    base_url: str,
    output_dir: Path,
    viewport_name: str,
) -> dict[str, str]:
    scenario_id = f"{viewport_name}-{time.time_ns()}"
    account_name = f"UI Audit Cash {scenario_id}"
    rule_category_name = "UI Audit Food"
    property_name = f"UI Audit Apartment {scenario_id}"
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
        account_card = page.locator(".entity-card").filter(has_text=account_name).first
        account_detail_path = account_card.locator('a[href^="/accounts/"]').first.get_attribute(
            "href"
        )

        page.goto(build_url(base_url, "/ledger/manual"), wait_until="domcontentloaded")
        page.locator("label.segmented-expense").click(timeout=PAGE_TIMEOUT_MS)
        page.locator('input[name="operation_date"]').fill("30.06.2026")
        page.locator('input[name="amount"]').fill("881.12")
        page.locator('input[name="description"]').fill("UI Audit expense")
        page.locator('form#new-manual-operation button[type="submit"]').click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.wait_for_url("**/ledger/manual?operation_id=**", timeout=PAGE_TIMEOUT_MS)
        manual_target_path = page.url.replace(base_url.rstrip("/"), "")

        page.goto(build_url(base_url, "/categories"), wait_until="domcontentloaded")
        open_details_if_closed(page, "details.category-create-details")
        category_form = page.locator('form[action="/categories"]').first
        category_form.locator('input[name="name"]').fill(rule_category_name)
        category_form.locator('select[name="kind"]').select_option("expense")
        category_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text(rule_category_name, exact=True).first.wait_for(timeout=PAGE_TIMEOUT_MS)

        page.goto(build_url(base_url, "/properties"), wait_until="domcontentloaded")
        open_details_if_closed(page, "details.property-create-details")
        property_form = page.locator('form[action="/properties"]').first
        property_form.locator('input[name="name"]').fill(property_name)
        property_form.locator('input[name="short_name"]').fill("UI Apt")
        property_form.locator('input[name="address"]').fill("Audit street, 1")
        property_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text(property_name, exact=True).first.wait_for(timeout=PAGE_TIMEOUT_MS)

        page.goto(build_url(base_url, "/rules"), wait_until="domcontentloaded")
        page.locator("details.rule-create-details > summary").click(timeout=PAGE_TIMEOUT_MS)
        rule_form = page.locator("form#new-rule")
        rule_form.locator('input[name="pattern"]').fill("OZON")
        rule_form.locator('select[name="target_operation_type"]').select_option("expense")
        rule_form.locator('select[name="category_id"]').select_option(label=rule_category_name)
        rule_form.locator("details.rule-advanced-details summary").click(timeout=PAGE_TIMEOUT_MS)
        rule_form.locator('select[name="direction"]').select_option("outflow")
        rule_form.locator('select[name="application_mode"]').select_option("suggest")
        rule_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.locator(".rule-card__title").get_by_text(
            f"OZON -> {rule_category_name}",
            exact=True,
        ).first.wait_for(timeout=PAGE_TIMEOUT_MS)

        page.goto(build_url(base_url, "/workspaces"), wait_until="domcontentloaded")
        page.locator("#workspace-invitation-create > summary").click(timeout=PAGE_TIMEOUT_MS)
        invitation_form = page.locator('form[action$="/invitations"]').first
        invitation_form.locator('select[name="role"]').select_option("viewer")
        invitation_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text("Ссылка-приглашение создана", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text("Ожидающие приглашения", exact=True).wait_for(timeout=PAGE_TIMEOUT_MS)

        page.goto(build_url(base_url, "/imports/upload"), wait_until="domcontentloaded")
        page.locator('input[name="statement_pdf"]').set_input_files(str(workbook_path))
        page.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.wait_for_url("**/imports/documents/**", timeout=PAGE_TIMEOUT_MS)
        detail_path = page.url.replace(base_url.rstrip("/"), "")
    finally:
        page.close()

    return {
        "account_name": account_name,
        "account_detail_path": account_detail_path or "",
        "manual_target_path": manual_target_path,
        "document_detail_path": detail_path,
        "mapping_path": f"{detail_path.rstrip('/')}/mapping",
        "document_name": document_name,
        "rule_category_name": rule_category_name,
        "property_name": property_name,
        "workspace_pending_invitation": "true",
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
            document_card = page.locator(".import-document-card, .entity-card").filter(
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


def prepare_design_audit_page(page: Page) -> None:
    page.evaluate(
        """
        () => {
          const selectors = [
            'details.account-create-details',
            'details.account-settings-details',
            'details.filter-details',
            'details.compact-help-details',
            'details.operation-edit-details',
          ];
          for (const selector of selectors) {
            for (const details of document.querySelectorAll(selector)) {
              details.open = true;
            }
          }
        }
        """
    )
    page.wait_for_timeout(100)


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

    if scenario == "realistic" and path == scenario_state.get("manual_target_path"):
        errors.extend(assert_manual_ledger_interactions(page))

    if path == "/_next/foundation":
        errors.extend(assert_frontend_next_foundation(page))

    if path == "/_next/ledger/manual":
        errors.extend(assert_frontend_next_manual_ledger(page, scenario=scenario))

    if path == "/app/ledger/manual":
        errors.extend(
            assert_react_manual_ledger(
                page,
                base_url=base_url,
                scenario=scenario,
                scenario_state=scenario_state,
            )
        )

    if (
        scenario == "realistic"
        and path == "/workspaces"
        and scenario_state.get("workspace_pending_invitation")
    ):
        body_text = page.locator("body").inner_text(timeout=PAGE_TIMEOUT_MS)
        if "Ожидающие приглашения" not in body_text:
            errors.append("workspaces page does not show seeded pending invitation")

    if scenario == "review_interactions" and path == scenario_state.get("review_path"):
        errors.extend(assert_review_interactions(page, scenario_state=scenario_state))

    if scenario == "button_audit":
        errors.extend(assert_safe_click_interactions(page, base_url=base_url))

    if scenario == "design_audit":
        errors.extend(assert_design_quality(page, path=path))

    return errors


def assert_manual_ledger_interactions(page: Page) -> list[str]:
    errors: list[str] = []
    targeted_row = page.locator(".manual-operation-row--target").first
    if targeted_row.count() == 0:
        return ["manual ledger target row was not found after create redirect"]

    row_id = targeted_row.get_attribute("id")
    if not row_id:
        return ["manual ledger target row has no stable id"]
    row = page.locator(f"#{row_id}")
    if row.locator('form[id^="manual-operation-form-"]').count() != 0:
        errors.append("manual ledger eagerly rendered a closed edit form")

    edit_button = row.locator("button.action-edit").first
    if edit_button.count() == 0:
        return [*errors, "manual ledger edit action was not found"]
    edit_button.click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.locator(".manual-operation-edit-panel-content").wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        errors.append(f"manual ledger edit panel did not open: {short_error(exc)}")
        return errors

    if not row.evaluate("element => element.classList.contains('entity-card--working')"):
        errors.append("manual ledger row did not enter working state after edit")
    if row.evaluate("element => element.classList.contains('manual-operation-row--target')"):
        errors.append("manual ledger target state was not cleared after edit")
    overflow = collect_overflow(page)
    if int(overflow["horizontalOverflowPx"]) > 1:
        errors.append("manual ledger open edit panel causes horizontal overflow")
    return errors


def assert_frontend_next_foundation(page: Page) -> list[str]:
    errors: list[str] = []
    row = page.locator("#foundation-row")
    if row.count() == 0:
        return ["Frontend Next foundation row was not found"]
    if row.evaluate("element => element.classList.contains('workbench-row--working')"):
        errors.append("Frontend Next row starts in working state before interaction")
    if row.locator("[data-edit-panel]").count() != 0:
        errors.append("Frontend Next foundation eagerly rendered the edit panel")

    disclosure = row.locator("a[aria-controls='foundation-edit-panel']")
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.locator("[data-edit-panel]").wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        errors.append(f"Frontend Next disclosure did not load: {short_error(exc)}")
        return errors
    if not row.evaluate("element => element.classList.contains('workbench-row--working')"):
        errors.append("Frontend Next row did not enter working state")
    overflow = collect_overflow(page)
    if int(overflow["horizontalOverflowPx"]) > 1:
        errors.append("Frontend Next open expansion panel causes horizontal overflow")
    return errors


def assert_frontend_next_manual_ledger(page: Page, *, scenario: str) -> list[str]:
    errors: list[str] = []
    if page.locator(".manual-ledger-filters").count() == 0:
        errors.append("Frontend Next manual ledger filters were not found")
    if page.locator(".financial-row, .manual-operation-row").count() != 0:
        errors.append("Frontend Next manual ledger rendered legacy row classes")
    if (
        page.locator(
            'form[id^="manual-operation-form-"], form[id^="next-manual-operation-form-"]'
        ).count()
        != 0
    ):
        errors.append("Frontend Next manual ledger eagerly rendered edit forms")

    rows = page.locator(".manual-ledger-row")
    if scenario == "realistic" and rows.count() == 0:
        errors.append("Frontend Next manual ledger did not render seeded operations")
    if scenario == "realistic" and rows.count() > 0:
        errors.extend(assert_frontend_next_manual_create(page))
        errors.extend(assert_frontend_next_manual_lifecycle(page, rows.first))
        errors.extend(assert_frontend_next_manual_reference_filters(page))
        viewport = page.viewport_size or {}
        if int(viewport.get("width") or 0) >= 1200:
            errors.extend(assert_frontend_next_manual_conflict(page, rows.first))
        errors.extend(assert_frontend_next_manual_edit(page, rows.first))
    overflow = collect_overflow(page)
    if int(overflow["horizontalOverflowPx"]) > 1:
        errors.append("Frontend Next manual ledger causes horizontal overflow")
    return errors


def assert_react_manual_ledger(
    page: Page,
    *,
    base_url: str,
    scenario: str,
    scenario_state: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    if page.get_by_role("heading", name="Ручные операции", exact=True).count() == 0:
        return ["React manual ledger heading was not found"]
    if page.locator(".financial-row, .manual-operation-row, .manual-ledger-row").count() != 0:
        errors.append("React manual ledger rendered legacy row classes")

    disclosure = page.get_by_role("button", name="Показать", exact=True)
    if disclosure.count() == 0:
        errors.append("React manual ledger filter disclosure was not found")
    else:
        disclosure.click(timeout=PAGE_TIMEOUT_MS)
        panel = page.locator("#manual-ledger-filter-panel")
        try:
            panel.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
        except PlaywrightError as exc:
            errors.append(f"React manual ledger filters did not open: {short_error(exc)}")
        else:
            for control_id in (
                "manual-filter-search",
                "manual-filter-date-from",
                "manual-filter-date-to",
                "manual-filter-type",
                "manual-filter-status",
                "manual-filter-account",
                "manual-filter-category",
                "manual-filter-property",
                "manual-filter-per-page",
            ):
                if panel.locator(f"#{control_id}").count() == 0:
                    errors.append(f"React manual ledger filter {control_id} was not found")

    rows = page.locator('article[id^="operation-"]')
    if scenario == "realistic" and rows.count() == 0:
        errors.append("React manual ledger did not render seeded operations")
    if rows.count() > 0:
        first = rows.first
        if first.locator("time[datetime]").count() == 0:
            errors.append("React manual ledger row has no semantic operation date")
        if first.locator("h2").count() == 0:
            errors.append("React manual ledger row has no primary description")

    target_path = scenario_state.get("manual_target_path")
    if scenario == "realistic" and target_path and "?" in target_path:
        target_search = target_path[target_path.index("?") :]
        page.goto(
            f"{base_url}/app/ledger/manual{target_search}",
            wait_until="networkidle",
            timeout=PAGE_TIMEOUT_MS,
        )
        target = page.locator('article[data-state="target"]')
        if target.count() != 1:
            errors.append("React manual ledger deep link did not mark one target row")
        target_disclosure = page.get_by_role("button", name="Показать", exact=True)
        if target_disclosure.count() == 1:
            target_disclosure.click(timeout=PAGE_TIMEOUT_MS)
        reset = page.get_by_role("link", name="Сбросить", exact=True)
        if reset.count() == 0 or reset.get_attribute("href") != "/app/ledger/manual":
            errors.append("React manual ledger reset link leaves the React route")

    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React manual ledger causes horizontal overflow")
    return errors


def assert_frontend_next_manual_create(page: Page) -> list[str]:
    errors: list[str] = []
    create_region = page.locator("#manual-ledger-create")
    disclosure = create_region.locator('a[aria-controls="manual-ledger-create-panel"]')
    if disclosure.count() == 0:
        return ["Frontend Next manual create disclosure was not found"]
    total_before = int(page.locator("#manual-ledger-total").inner_text().split()[0])
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    form = create_region.locator("#next-manual-operation-create-form")
    try:
        form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"Frontend Next manual create panel did not load: {short_error(exc)}"]
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("Frontend Next manual create panel causes horizontal overflow")

    account = form.locator('select[name="account_id"]')
    if account.locator("option").count() < 2:
        return [*errors, "Frontend Next manual create form has no account option"]
    account.select_option(index=1)
    amount = form.locator('input[name="amount"]')
    amount.fill("0")
    form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    try:
        create_region.get_by_text("Сумма должна быть больше нуля.").wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual create 422 state was not rendered: {short_error(exc)}")
        return errors

    amount_box = create_region.locator('input[name="amount"]').bounding_box()
    date_box = create_region.locator('input[name="operation_date"]').bounding_box()
    if amount_box and date_box and abs(amount_box["height"] - date_box["height"]) > 1:
        errors.append("Frontend Next manual field error stretched the neighboring control")

    form = create_region.locator("#next-manual-operation-create-form")
    form.locator('input[name="amount"]').fill("123.45")
    description = "UI audit: созданная операция"
    form.locator('input[name="description"]').fill(description)
    form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    try:
        form.wait_for(state="detached", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual create did not replace the list: {short_error(exc)}")
        return errors

    total_after = int(page.locator("#manual-ledger-total").inner_text().split()[0])
    if total_after != total_before + 1:
        errors.append("Frontend Next manual create did not update the OOB total")
    if create_region.locator("#next-manual-operation-create-form").count() != 0:
        errors.append("Frontend Next manual create form stayed open after success")
    if page.locator(".manual-ledger-row [data-expansion-panel]:visible").count() != 0:
        errors.append("Frontend Next manual create opened an unrelated edit panel")
    return errors


def assert_frontend_next_manual_lifecycle(page: Page, row: Locator) -> list[str]:
    errors: list[str] = []
    row_id = row.get_attribute("id")
    if not row_id:
        return ["Frontend Next manual lifecycle row has no stable id"]
    row = page.locator(f"#{row_id}")
    total_before = int(page.locator("#manual-ledger-total").inner_text().split()[0])

    more_actions = row.locator("details.action-stack__more > summary")
    if more_actions.count() == 0:
        return ["Frontend Next manual cancel action menu was not found"]
    more_actions.click(timeout=PAGE_TIMEOUT_MS)
    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button", name="Отменить операцию").click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.get_by_text("отменено", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"Frontend Next manual cancel did not replace the row: {short_error(exc)}"]

    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button", name="Восстановить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.get_by_text("подтверждено", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"Frontend Next manual restore did not replace the row: {short_error(exc)}"]

    row.locator("details.action-stack__more > summary").click(timeout=PAGE_TIMEOUT_MS)
    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button", name="Отменить операцию").click(timeout=PAGE_TIMEOUT_MS)
    row.get_by_text("отменено", exact=True).wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )
    row.locator("details.action-stack__more > summary").click(timeout=PAGE_TIMEOUT_MS)
    page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_role("button", name="Удалить окончательно").click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.wait_for(state="detached", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual delete did not rebuild the list: {short_error(exc)}")
        return errors

    total_after = int(page.locator("#manual-ledger-total").inner_text().split()[0])
    if total_after != total_before - 1:
        errors.append("Frontend Next manual delete did not update the OOB total")
    try:
        page.locator("#manual-ledger-results:focus, #manual-ledger-results :focus").first.wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError:
        errors.append("Frontend Next manual delete did not restore focus")
    return errors


def assert_frontend_next_manual_reference_filters(page: Page) -> list[str]:
    form = page.locator(".manual-ledger-filters")
    filter_names = ("account_id", "category_id", "property_id")
    selected_values: dict[str, str] = {}
    for name in filter_names:
        select = form.locator(f'select[name="{name}"]')
        if select.count() == 0:
            return [f"Frontend Next manual {name} filter was not found"]
        if select.locator("option").count() < 2:
            continue
        selected = select.locator("option").nth(1).get_attribute("value")
        if selected:
            select.select_option(selected)
            selected_values[name] = selected

    if not selected_values:
        return ["Frontend Next manual reference filters have no realistic options"]
    form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    for name, expected in selected_values.items():
        if page.locator(f'.manual-ledger-filters select[name="{name}"]').input_value() != expected:
            return [f"Frontend Next manual {name} filter did not survive GET"]
        if f"{name}={expected}" not in page.url:
            return [f"Frontend Next manual {name} filter was lost from URL"]

    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        return ["Frontend Next manual reference filters cause horizontal overflow"]
    page.get_by_role("link", name="Сбросить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    return []


def assert_frontend_next_manual_conflict(page: Page, row: Locator) -> list[str]:
    row_id = row.get_attribute("id")
    if not row_id:
        return ["Frontend Next manual conflict row has no stable id"]
    row = page.locator(f"#{row_id}")
    disclosure = row.locator('a[aria-controls^="next-manual-operation-edit-panel-"]').first
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    stale_form = row.locator('form[id^="next-manual-operation-form-"]')
    stale_form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    stale_version = stale_form.locator('input[name="version"]').input_value()
    user_draft = "UI audit: несохранённый конкурентный черновик"
    concurrent_value = "UI audit: изменение из второй вкладки"
    stale_form.locator('input[name="description"]').fill(user_draft)

    concurrent_page = page.context.new_page()
    try:
        concurrent_page.goto(page.url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        concurrent_row = concurrent_page.locator(f"#{row_id}")
        concurrent_row.locator('a[aria-controls^="next-manual-operation-edit-panel-"]').first.click(
            timeout=PAGE_TIMEOUT_MS
        )
        concurrent_form = concurrent_row.locator('form[id^="next-manual-operation-form-"]')
        concurrent_form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
        concurrent_form.locator('input[name="description"]').fill(concurrent_value)
        concurrent_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        concurrent_form.wait_for(state="detached", timeout=PAGE_TIMEOUT_MS)

        stale_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        try:
            row.get_by_text("Операция уже изменилась в другом окне").wait_for(
                state="visible",
                timeout=PAGE_TIMEOUT_MS,
            )
        except PlaywrightError as exc:
            return [f"Frontend Next manual 409 conflict was not rendered: {short_error(exc)}"]

        conflict_form = row.locator('form[id^="next-manual-operation-form-"]')
        if conflict_form.locator('input[name="description"]').input_value() != user_draft:
            return ["Frontend Next manual conflict did not preserve the user draft"]
        if conflict_form.locator('input[name="version"]').input_value() != stale_version:
            return ["Frontend Next manual conflict replaced the submitted version prematurely"]

        row.get_by_role("link", name="Загрузить актуальную версию").click(timeout=PAGE_TIMEOUT_MS)
        page.wait_for_function(
            """
            ({ rowId, expected }) => {
              const input = document.querySelector(`#${rowId} input[name="description"]`);
              return input instanceof HTMLInputElement && input.value === expected;
            }
            """,
            arg={"rowId": row_id, "expected": concurrent_value},
            timeout=PAGE_TIMEOUT_MS,
        )
        fresh_form = row.locator('form[id^="next-manual-operation-form-"]')
        if fresh_form.locator('input[name="version"]').input_value() == stale_version:
            return ["Frontend Next manual conflict reload kept the stale version"]
        row.get_by_text("Закрыть", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    finally:
        concurrent_page.close()
    return []


def assert_frontend_next_manual_edit(page: Page, row: Locator) -> list[str]:
    errors: list[str] = []
    row_id = row.get_attribute("id")
    disclosure = row.locator('a[aria-controls^="next-manual-operation-edit-panel-"]').first
    if disclosure.count() == 0:
        return ["Frontend Next manual edit disclosure was not found"]
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    panel_id = disclosure.get_attribute("aria-controls")
    if not panel_id:
        return ["Frontend Next manual edit disclosure has no panel target"]
    panel = page.locator(f"#{panel_id}")
    form = row.locator('form[id^="next-manual-operation-form-"]')
    try:
        form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"Frontend Next manual edit panel did not load: {short_error(exc)}"]
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("Frontend Next manual edit panel causes horizontal overflow")

    close = panel.get_by_text("Закрыть", exact=True)
    if close.count() == 0:
        errors.append("Frontend Next manual close action was lost after lazy load")
        return errors
    close.click(timeout=PAGE_TIMEOUT_MS)
    try:
        panel.wait_for(state="hidden", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual panel did not close: {short_error(exc)}")
        return errors
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)

    original_description = form.locator('input[name="description"]').input_value().strip()
    amount = form.locator('input[name="amount"]')
    original_amount = amount.input_value()
    amount.fill("0")
    form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.get_by_text("Сумма должна быть больше нуля.").wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual 422 state was not rendered: {short_error(exc)}")
        return errors
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("Frontend Next manual 422 state causes horizontal overflow")

    amount = row.locator('form[id^="next-manual-operation-form-"] input[name="amount"]')
    if amount.input_value() != "0":
        errors.append("Frontend Next manual validation did not preserve the amount draft")
    amount.fill(original_amount)
    row.locator('form[id^="next-manual-operation-form-"] button[type="submit"]').click(
        timeout=PAGE_TIMEOUT_MS
    )
    try:
        row.locator('form[id^="next-manual-operation-form-"]').wait_for(
            state="detached",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        errors.append(f"Frontend Next manual row was not replaced after save: {short_error(exc)}")
        return errors

    if not row.evaluate("element => element.classList.contains('workbench-row--working')"):
        errors.append("Frontend Next manual row did not retain working feedback after save")
    try:
        row.locator(":focus").wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError:
        errors.append("Frontend Next manual row did not restore focus after save")
    if panel.is_visible():
        errors.append("Frontend Next manual panel stayed open after replaceRow")
    if panel.get_by_text("Загружаем форму…").is_visible():
        errors.append("Frontend Next manual loading placeholder stayed visible after save")

    if row_id and original_description:
        search = page.locator('.manual-ledger-filters input[name="search"]')
        search.fill(original_description)
        page.locator('.manual-ledger-filters button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        filtered_row = page.locator(f"#{row_id}")
        try:
            filtered_row.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
        except PlaywrightError as exc:
            errors.append(f"Frontend Next manual filtered row was not rendered: {short_error(exc)}")
            return errors

        total_before = int(page.locator("#manual-ledger-total").inner_text().split()[0])
        filtered_row.locator('a[aria-controls^="next-manual-operation-edit-panel-"]').first.click(
            timeout=PAGE_TIMEOUT_MS
        )
        filtered_form = filtered_row.locator('form[id^="next-manual-operation-form-"]')
        filtered_form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
        filtered_form.locator('input[name="description"]').fill("UI audit: проверка области ответа")
        filtered_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        try:
            filtered_row.wait_for(state="detached", timeout=PAGE_TIMEOUT_MS)
        except PlaywrightError as exc:
            errors.append(
                f"Frontend Next manual row stayed in a mismatched filtered list: {short_error(exc)}"
            )
            return errors

        total_after = int(page.locator("#manual-ledger-total").inner_text().split()[0])
        if total_after != total_before - 1:
            errors.append("Frontend Next manual OOB total did not follow replaceList")
        focused_in_results = page.locator(
            "#manual-ledger-results:focus, #manual-ledger-results :focus"
        )
        if focused_in_results.count() == 0:
            errors.append("Frontend Next manual replaceList did not restore focus")
    return errors


def assert_design_quality(page: Page, *, path: str) -> list[str]:
    state = page.evaluate(
        """
        () => {
          const visible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            let ancestor = element.parentElement;
            while (ancestor) {
              if (ancestor.matches('details:not([open])')) {
                const summary = ancestor.querySelector(':scope > summary');
                if (element !== summary && !summary?.contains(element)) {
                  return false;
                }
              }
              ancestor = ancestor.parentElement;
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
            const details = summary.closest('details.technical-details');
            return {
              text: textFor(summary),
              detailsText: details ? textFor(details).slice(0, 80) : '',
              className: details ? String(details.className || '') : '',
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
            .filter((item) => item.maxRadius > 8)
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

          const accordionOverflow = Array.from(
            document.querySelectorAll('details.action-accordion[open]')
          ).flatMap((details, index) => {
            const containerRect = details.getBoundingClientRect();
            return Array.from(details.children)
              .filter((element) => element.tagName.toLowerCase() !== 'summary')
              .filter(visible)
              .map((element) => {
                const rect = element.getBoundingClientRect();
                return {
                  index: index + 1,
                  className: String(element.className || ''),
                  label: textFor(details.querySelector(':scope > summary')),
                  left: Math.round(rect.left),
                  right: Math.round(rect.right),
                  containerLeft: Math.round(containerRect.left),
                  containerRight: Math.round(containerRect.right),
                };
              })
              .filter((item) => (
                item.left < item.containerLeft - 1
                || item.right > item.containerRight + 1
              ));
          });

          const entryMoneyIssues = Array.from(document.querySelectorAll('.entry-money'))
            .filter(visible)
            .map((element) => {
              const text = textFor(element);
              const className = String(element.className || '');
              return { text, className };
            })
            .filter((item) => {
              const normalized = item.text.replace(/\\s+/g, '');
              if (normalized.startsWith('-')) {
                return !item.className.includes('money-expense');
              }
              if (normalized.startsWith('0') || normalized.startsWith('+0')) {
                return !item.className.includes('money-transfer');
              }
              return !item.className.includes('money-income');
            });

          return {
            pageControls,
            blockIssues,
            technicalSummaries,
            badgeMetrics,
            radiusOffenders,
            visibleDebugBlocks,
            webOneControlLabels,
            accordionOverflow,
            entryMoneyIssues,
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
        examples = ", ".join(
            (
                f"{item.get('text') or item.get('detailsText') or '<empty>'} "
                f"[{item.get('className')}; {item.get('height')}px]"
            )
            for item in noisy_technical[:3]
        )
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
        errors.append("designer audit: rounded corners exceed 8px design limit: " + examples)

    visible_debug_blocks = list(state.get("visibleDebugBlocks") or [])
    if visible_debug_blocks:
        errors.append(
            "designer audit: raw debug/code blocks are visible by default "
            f"({len(visible_debug_blocks)} blocks); hide them behind debug details"
        )

    accordion_overflow = list(state.get("accordionOverflow") or [])
    if accordion_overflow:
        examples = ", ".join(
            f"{item.get('label')} ({item.get('className')})" for item in accordion_overflow[:3]
        )
        errors.append("designer audit: expanded accordion content escapes its border: " + examples)

    entry_money_issues = list(state.get("entryMoneyIssues") or [])
    if entry_money_issues:
        examples = ", ".join(
            f"{item.get('text')} ({item.get('className')})" for item in entry_money_issues[:3]
        )
        errors.append("designer audit: operation amount color class is wrong: " + examples)

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
    if row.locator(".review-item__ledger-summary--suggested").count() == 0:
        errors.append("suggested review row does not show proposed outcome summary")
    else:
        suggested_summary = row.locator(".review-item__ledger-summary--suggested").first.inner_text(
            timeout=PAGE_TIMEOUT_MS
        )
        if "предложено" not in suggested_summary.casefold():
            errors.append("proposed outcome summary does not show suggested state")
        rule_category_name = scenario_state.get("rule_category_name")
        if rule_category_name and rule_category_name not in suggested_summary:
            errors.append("proposed outcome summary does not show suggested category")

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

    category_toggle = row.locator(".review-panel__tab--category:visible").first
    if category_toggle.count() == 0:
        category_toggle = row.locator(".action-category_panel:visible").first
    if category_toggle.count() == 0:
        errors.append("category panel trigger was not found")
        return errors
    category_toggle.click()
    if (
        category_toggle.evaluate("element => element.classList.contains('review-panel__tab')")
        and category_toggle.get_attribute("aria-expanded") != "true"
    ):
        errors.append("category panel did not open")
    try:
        row.locator(".review-panel__drawer:visible").first.wait_for(timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError:
        pass
    if row.locator(".review-panel__drawer:visible").count() != 1:
        errors.append("category panel opening did not leave exactly one visible drawer")
    try:
        row.locator(".inline-create-button").first.wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError:
        errors.append("category panel content did not load")
        return errors

    row.locator(".inline-create-button").first.click()
    dialog = row.locator("dialog.review-category-dialog")
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
    refreshed_category_toggle = refreshed_row.locator(".review-panel__tab--category:visible").first
    if refreshed_category_toggle.count() == 0:
        refreshed_category_toggle = refreshed_row.locator(".action-category_panel:visible").first
    if refreshed_category_toggle.count() == 0:
        errors.append("category panel trigger was not found after category creation")
    elif (
        refreshed_category_toggle.evaluate(
            "element => element.classList.contains('review-panel__tab')"
        )
        and refreshed_category_toggle.get_attribute("aria-expanded") != "true"
    ):
        errors.append("category panel did not stay open after category creation")
    try:
        refreshed_row.locator(".review-panel__drawer:visible").first.wait_for(
            timeout=PAGE_TIMEOUT_MS
        )
    except PlaywrightError:
        pass
    if refreshed_row.locator(".review-panel__drawer:visible").count() != 1:
        errors.append("category panel refresh did not leave exactly one visible drawer")
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
    if confirmed_row.locator(".review-item__ledger-summary").count() == 0:
        errors.append("confirmed review row does not show operation reference")
    correction_action = confirmed_row.locator(".review-actions__correction").first
    if correction_action.count() == 0:
        errors.append("confirmed review row does not expose correction action")
    else:
        correction_action.locator("summary").click()
        undo_button = correction_action.locator("button.action-undo_posting").first
        if undo_button.count() == 0:
            errors.append("confirmed review row does not expose undo posting action")
        else:
            page.once("dialog", lambda dialog: dialog.dismiss())
            undo_button.click()
            page.wait_for_timeout(500)
            if confirmed_row.locator(".review-item__ledger-summary--confirmed").count() == 0:
                errors.append("undo posting continued after canceling confirmation dialog")
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
        if scenario == "design_audit":
            prepare_design_audit_page(page)
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
        console_errors = remove_expected_console_error(
            console_errors,
            path=path,
            scenario=scenario,
            ux_assertion_errors=ux_assertion_errors,
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


def remove_expected_console_error(
    errors: list[str],
    *,
    path: str,
    scenario: str,
    ux_assertion_errors: list[str],
) -> list[str]:
    filtered = list(errors)
    if path != "/_next/ledger/manual" or scenario != "realistic":
        return filtered
    if any("422 state was not rendered" in error for error in ux_assertion_errors):
        return filtered
    conflict_rendered = not any(
        "409 conflict was not rendered" in error for error in ux_assertion_errors
    )
    return [
        message
        for message in filtered
        if not (
            "Failed to load resource" in message
            and (
                "422 (Unprocessable Entity)" in message
                or (conflict_rendered and "409 (Conflict)" in message)
            )
        )
    ]


def run_audit(
    base_url: str,
    output_dir: Path,
    *,
    authenticated: bool,
    auth_email: str | None,
    auth_password: str,
    scenario: str,
    selected_paths: tuple[str, ...],
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
                    dynamic_pages: list[tuple[str, str]] = []
                    if scenario_state.get("account_detail_path"):
                        dynamic_pages.append(
                            (scenario_state["account_detail_path"], "account-detail")
                        )
                    if scenario_state.get("manual_target_path"):
                        dynamic_pages.append(
                            (scenario_state["manual_target_path"], "manual-operation-target")
                        )
                    if scenario_state.get("document_detail_path"):
                        dynamic_pages.append(
                            (scenario_state["document_detail_path"], "import-document-detail")
                        )
                    if scenario == "realistic" and scenario_state.get("mapping_path"):
                        dynamic_pages.append((scenario_state["mapping_path"], "import-mapping"))
                    if scenario in {
                        "review_interactions",
                        "button_audit",
                        "design_audit",
                    } and scenario_state.get("review_path"):
                        dynamic_pages.append((scenario_state["review_path"], "review-interactions"))
                    if dynamic_pages:
                        pages = (*pages, *dynamic_pages)
                    if selected_paths:
                        pages = tuple(page for page in pages if page[0] in selected_paths)
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
            selected_paths=tuple(args.paths or ()),
        )
        report_path = write_report(results, output_dir, scenario=args.scenario)
        print_summary(results, report_path)
        return 0 if all(result.passed for result in results) else 1
    finally:
        stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
