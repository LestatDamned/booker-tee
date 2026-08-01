from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import UUID

from openpyxl import Workbook
from playwright.sync_api import BrowserContext, Page, Route, sync_playwright
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
    ("/app/accounts", "accounts"),
    ("/ledger/manual", "manual-ledger-redirect"),
    ("/app/imports", "imports"),
    ("/app/imports/upload", "imports-upload"),
    ("/rules", "rules"),
    ("/categories", "categories"),
    ("/app/categories", "react-categories"),
    ("/properties", "properties-redirect"),
    ("/app/properties", "react-properties"),
    ("/users", "users"),
    ("/workspaces", "workspaces"),
)

AUTHENTICATED_PAGES: tuple[tuple[str, str], ...] = (
    ("/dashboard", "dashboard"),
    ("/app/ledger/manual", "react-manual-ledger"),
    ("/app/foundation", "react-foundation"),
    ("/app/reports", "react-reports"),
    ("/app/accounts", "accounts"),
    ("/ledger/manual", "manual-ledger-redirect"),
    ("/app/imports", "imports"),
    ("/app/imports/upload", "imports-upload"),
    ("/rules", "rules"),
    ("/reports?currency=RUB", "reports-redirect"),
    ("/categories", "categories"),
    ("/app/categories", "react-categories"),
    ("/properties", "properties-redirect"),
    ("/app/properties", "react-properties"),
    ("/users", "users"),
    ("/workspaces", "workspaces"),
)

VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop", 1440, 1000),
    ("tablet", 920, 900),
    ("mobile", 390, 844),
)

THEMES: tuple[str, ...] = ("catppuccin-mocha", "catppuccin-latte", "test")


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
    performance_metrics: dict[str, float | int]
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
            "theme_audit",
            "reports_stress",
        ),
        default="empty",
        help="Data scenario to prepare before auditing authenticated pages.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help=(
            "Audit only this path or stable page label. Repeat the option to select several pages."
        ),
    )
    parser.add_argument(
        "--theme",
        choices=THEMES,
        default="catppuccin-mocha",
        help="Force one React theme for screenshots and browser checks.",
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
    destination_account_name = f"UI Audit Savings {scenario_id}"
    rule_category_name = "UI Audit Food"
    property_name = f"UI Audit Apartment {scenario_id}"
    document_name = f"ui-audit-statement-{scenario_id}.xlsx"
    workbook_path = output_dir / document_name
    create_statement_fixture(workbook_path)

    page = context.new_page()
    try:
        page.goto(build_url(base_url, "/app/accounts"), wait_until="networkidle")
        page.get_by_role("button", name="Новый счёт", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        create_form = page.locator("form[data-account-create]")
        create_form.locator('input[name="name"]').fill(account_name)
        create_form.locator('select[name="accountType"]').select_option("cash")
        create_form.locator('input[name="currency"]').fill("RUB")
        create_form.locator('input[name="initialBalance"]').fill("10000.00")
        create_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        account_record = (
            page.locator("[data-account-record]:visible").filter(has_text=account_name).first
        )
        account_record.wait_for(timeout=PAGE_TIMEOUT_MS)
        account_detail_path = account_record.locator(
            'a[href^="/app/accounts/"]'
        ).first.get_attribute("href")
        page.goto(build_url(base_url, "/app/accounts"), wait_until="networkidle")
        page.get_by_role("button", name="Новый счёт", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        create_form = page.locator("form[data-account-create]")
        create_form.locator('input[name="name"]').fill(destination_account_name)
        create_form.locator('select[name="accountType"]').select_option("deposit")
        create_form.locator('input[name="currency"]').fill("RUB")
        create_form.locator('input[name="initialBalance"]').fill("0.00")
        create_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        (
            page.locator("[data-account-record]:visible")
            .filter(has_text=destination_account_name)
            .first.wait_for(timeout=PAGE_TIMEOUT_MS)
        )

        page.goto(build_url(base_url, "/app/ledger/manual"), wait_until="networkidle")
        page.get_by_role("button", name="Добавить операцию", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        create_form = page.locator("#manual-operation-create-panel")
        create_form.get_by_role("radio", name="Расход", exact=True).check()
        create_form.locator("#manual-operation-account").select_option(
            label=f"{account_name} · RUB"
        )
        create_form.locator("#manual-operation-date").fill("2026-06-30")
        create_form.locator("#manual-operation-amount").fill("881.12")
        create_form.locator("#manual-operation-description").fill("UI Audit expense")
        create_form.get_by_role("button", name="Создать расход", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.wait_for_url("**/app/ledger/manual?operation_id=**", timeout=PAGE_TIMEOUT_MS)
        manual_target_path = page.url.replace(base_url.rstrip("/"), "")

        page.goto(build_url(base_url, "/categories"), wait_until="domcontentloaded")
        open_details_if_closed(page, "details.category-create-details")
        category_form = page.locator('form[action="/categories"]').first
        category_form.locator('input[name="name"]').fill(rule_category_name)
        category_form.locator('select[name="kind"]').select_option("expense")
        category_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_text(rule_category_name, exact=True).first.wait_for(timeout=PAGE_TIMEOUT_MS)
        page.goto(build_url(base_url, "/app/categories"), wait_until="networkidle")
        category_record = (
            page.locator("[data-category-record]:visible").filter(has_text=rule_category_name).first
        )
        category_record.wait_for(timeout=PAGE_TIMEOUT_MS)
        category_detail_path = category_record.locator(
            "a[data-record-identity]"
        ).first.get_attribute("href")
        if category_detail_path and category_detail_path.startswith("/categories/"):
            category_detail_path = f"/app{category_detail_path}"
        if category_detail_path:
            page.goto(build_url(base_url, category_detail_path), wait_until="networkidle")
            page.get_by_role("button", name="Изменить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
            category_edit_form = page.locator("form[data-category-edit]:visible")
            category_edit_form.wait_for(timeout=PAGE_TIMEOUT_MS)
            page.screenshot(
                path=output_dir / f"{viewport_name}-category-edit-panel.png",
                full_page=True,
            )
            category_edit_form.locator('textarea[name="notes"]').fill("UI audit category edit")
            category_edit_form.get_by_role("button", name="Сохранить", exact=True).click(
                timeout=PAGE_TIMEOUT_MS
            )
            page.get_by_text(f"Категория «{rule_category_name}» изменена.", exact=True).wait_for(
                timeout=PAGE_TIMEOUT_MS
            )

        page.goto(build_url(base_url, "/app/properties"), wait_until="networkidle")
        page.get_by_role("button", name="Новый объект", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        property_form = page.locator("form[data-property-create]")
        property_form.locator('input[name="name"]').fill(property_name)
        property_form.locator('input[name="shortName"]').fill("UI Apt")
        property_form.locator('textarea[name="address"]').fill("Audit street, 1")
        property_form.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        (
            page.locator("[data-property-record]:visible")
            .filter(has_text=property_name)
            .first.wait_for(timeout=PAGE_TIMEOUT_MS)
        )
        property_record = (
            page.locator("[data-property-record]:visible").filter(has_text=property_name).first
        )
        property_record.get_by_role("button", name="Изменить", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        edit_form = page.locator("form[data-property-edit]:visible")
        property_name = f"{property_name} edited"
        edit_form.locator('input[name="name"]').fill(property_name)
        edit_form.get_by_role("button", name="Сохранить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        (
            page.locator("[data-property-record]:visible")
            .filter(has_text=property_name)
            .first.wait_for(timeout=PAGE_TIMEOUT_MS)
        )
        property_record = (
            page.locator("[data-property-record]:visible").filter(has_text=property_name).first
        )
        property_record.get_by_role("button", name="Ещё действия", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.get_by_role("button", name="В архив", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        archive_dialog = page.get_by_role("dialog", name="Перенести объект в архив?", exact=True)
        archive_dialog.get_by_role("button", name="Перенести в архив", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.get_by_role("link", name=re.compile(r"^Архив \d+$")).click(timeout=PAGE_TIMEOUT_MS)
        archived_record = (
            page.locator("[data-property-record]:visible").filter(has_text=property_name).first
        )
        archived_record.wait_for(timeout=PAGE_TIMEOUT_MS)
        archived_record.get_by_role("button", name="Ещё действия", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.get_by_role("button", name="Восстановить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role("link", name=re.compile(r"^Активные \d+$")).click(timeout=PAGE_TIMEOUT_MS)
        (
            page.locator("[data-property-record]:visible")
            .filter(has_text=property_name)
            .first.wait_for(timeout=PAGE_TIMEOUT_MS)
        )

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

        page.goto(build_url(base_url, "/app/imports/upload"), wait_until="domcontentloaded")
        page.locator('select[name="accountId"]').select_option(index=1)
        page.locator('input[name="statement"]').set_input_files(str(workbook_path))
        page.locator('button[type="submit"]').click(timeout=PAGE_TIMEOUT_MS)
        page.wait_for_url("**/app/imports/documents/**", timeout=PAGE_TIMEOUT_MS)
        detail_path = page.url.replace(base_url.rstrip("/"), "")
    finally:
        page.close()

    return {
        "account_name": account_name,
        "account_detail_path": account_detail_path or "",
        "category_detail_path": category_detail_path or "",
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
        if "/app/imports/documents/" not in detail_url:
            page.goto(build_url(base_url, "/app/imports"), wait_until="domcontentloaded")
            document_record = page.locator("tr:visible, article:visible").filter(
                has_text=scenario_state["document_name"]
            )
            document_record.wait_for(timeout=PAGE_TIMEOUT_MS)
            document_record.locator('a[href^="/app/imports/documents/"]').first.click()
            page.wait_for_url("**/app/imports/documents/**", timeout=PAGE_TIMEOUT_MS)
            detail_url = page.url

        mapping_url = f"{detail_url.rstrip('/')}/mapping"
        page.goto(mapping_url, wait_until="domcontentloaded")
        page.locator("#mapping-form").wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_label("Если у суммы нет знака *").select_option("income")
        page.get_by_role("button", name="Показать предпросмотр").click()
        page.get_by_role("heading", name="Предпросмотр строк").wait_for(timeout=PAGE_TIMEOUT_MS)
        page.get_by_role(
            "button",
            name=re.compile(r"^Импортировать \d+ строк"),
        ).click()
        page.wait_for_url("**/app/imports/documents/**/review", timeout=PAGE_TIMEOUT_MS)
        scenario_state["react_review_path"] = page.url.replace(base_url.rstrip("/"), "")
        scenario_state["historical_review_path"] = scenario_state["react_review_path"].replace(
            "/app/imports/documents/",
            "/imports/documents/",
            1,
        )
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
            '[data-account-create]',
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
    theme: str,
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
        if "/app/ledger/manual" not in page.url:
            errors.append("manual operation target did not open the canonical React route")
        elif page.locator('article[data-state="target"]').count() != 1:
            errors.append("manual operation target did not mark one React row")

    if path == "/ledger/manual" and "/app/ledger/manual" not in page.url:
        errors.append("historical manual ledger URL did not redirect to React")

    if path == "/app/ledger/manual":
        errors.extend(
            assert_react_manual_ledger(
                page,
                base_url=base_url,
                scenario=scenario,
                scenario_state=scenario_state,
            )
        )

    if path == "/app/reports":
        errors.extend(assert_react_reports(page))
        if scenario == "reports_stress":
            errors.extend(assert_react_reports_stress(page))

    if path.startswith("/reports") and "/app/reports" not in page.url:
        errors.append("historical Reports URL did not redirect to React")

    if scenario == "realistic" and path == scenario_state.get("account_detail_path"):
        errors.extend(assert_react_account_management(page))

    if (
        scenario == "realistic"
        and path == "/workspaces"
        and scenario_state.get("workspace_pending_invitation")
    ):
        body_text = page.locator("body").inner_text(timeout=PAGE_TIMEOUT_MS)
        if "Ожидающие приглашения" not in body_text:
            errors.append("workspaces page does not show seeded pending invitation")

    if scenario == "review_interactions" and path == scenario_state.get("historical_review_path"):
        if "/app/imports/documents/" not in page.url:
            errors.append("historical import review URL did not redirect to React")

    if scenario == "review_interactions" and path == scenario_state.get("react_review_path"):
        errors.extend(assert_react_import_review(page))

    if scenario == "button_audit":
        errors.extend(assert_safe_click_interactions(page, base_url=base_url))

    if scenario == "design_audit":
        errors.extend(assert_design_quality(page, path=path))

    if scenario == "theme_audit":
        errors.extend(
            assert_react_theme(
                page,
                path=path,
                scenario_state=scenario_state,
                theme=theme,
            )
        )

    return errors


def assert_react_reports(page: Page) -> list[str]:
    errors: list[str] = []
    try:
        page.get_by_role("heading", name="Отчёты", exact=True).wait_for(
            state="visible", timeout=PAGE_TIMEOUT_MS * 2
        )
    except PlaywrightError as exc:
        return [f"React Reports did not finish loading: {short_error(exc)}"]

    if page.get_by_role("heading", name="Деньги по категориям", exact=True).count() != 1:
        errors.append("React Reports category flow heading was not found")
    if page.get_by_role("navigation", name="Раздел отчёта").count() != 0:
        errors.append("React Reports still exposes superseded breakdown navigation")
    if page.get_by_role("navigation", name="Показатель отчёта").count() != 0:
        errors.append("React Reports still exposes superseded metric navigation")
    category_table = page.get_by_role("table", name="Поступления, расходы и итог по категориям")
    if category_table.count() == 1 and category_table.is_visible():
        for label in ("Категория", "Поступления", "Расходы", "Итог"):
            if page.get_by_role("link", name=re.compile(f"^{label}: сортировать по ")).count() != 1:
                errors.append(f"React Reports direct category sort is not visible: {label}")
    if page.get_by_text(re.compile("^Все суммы в ")).count() != 0:
        errors.append("React Reports still exposes redundant category currency text")
    if page.get_by_text("Сначала", exact=True).count() != 0:
        errors.append("React Reports still exposes redundant category sort control")
    category_matrix_views = (
        page.get_by_role("table", name="Поступления, расходы и итог по категориям").count()
        + page.get_by_role("list", name="Движение денег по категориям").count()
        + page.get_by_text(
            "За выбранный период нет доходов или расходов по категориям.",
            exact=True,
        ).count()
    )
    if category_matrix_views != 1:
        errors.append("React Reports unified category matrix state was not found")
    if page.get_by_role("region", name="Итог периода").count() != 1:
        errors.append("React Reports period summary was not found")
    if page.get_by_role("region", name="Распределение денег по счетам").count() != 1:
        errors.append("React Reports account supporting pane was not found")
    account_balance_views = (
        page.get_by_role("table", name="Остатки по счетам за период").count()
        + page.get_by_role("list", name="Остатки по счетам за период").count()
    )
    if account_balance_views != 1:
        errors.append("React Reports account balance comparison was not found")
    account_drilldown = page.locator('[data-record-identity][href^="/app/accounts/"]:visible').first
    if account_drilldown.count() != 1:
        errors.append("React Reports account drill-down was not found")
    else:
        account_href = account_drilldown.get_attribute("href") or ""
        if "status=confirmed" not in account_href or "return_to=" not in account_href:
            errors.append("React Reports account drill-down loses report context")
    if page.get_by_role("link", name="Разобрать", exact=True).count() != 1:
        errors.append("React Reports compact correction target was not found")

    if page.locator("html").evaluate("element => element.scrollWidth > element.clientWidth"):
        errors.append("React Reports causes horizontal page overflow")
    errors.extend(assert_react_reports_ultrawide_layout(page))
    errors.extend(assert_react_reports_keyboard_and_reflow(page))
    return errors


def assert_react_reports_ultrawide_layout(page: Page) -> list[str]:
    errors: list[str] = []
    viewport = page.viewport_size or {}
    width = int(viewport.get("width") or 0)
    height = int(viewport.get("height") or 0)
    if width < 1200 or height == 0:
        return errors

    try:
        for audit_width, audit_height in ((1920, 1080), (2560, 1440)):
            page.set_viewport_size({"width": audit_width, "height": audit_height})
            page.wait_for_timeout(100)
            usage = page.locator("[data-report-workspace]").evaluate(
                """element => ({
                    frameWidth: element.getBoundingClientRect().width,
                    parentContentWidth: (() => {
                        const parent = element.parentElement;
                        const style = getComputedStyle(parent);
                        return parent.clientWidth
                            - Number.parseFloat(style.paddingLeft)
                            - Number.parseFloat(style.paddingRight);
                    })(),
                })"""
            )
            if float(usage["frameWidth"]) < float(usage["parentContentWidth"]) * 0.98:
                errors.append(f"React Reports does not use the workspace width at {audit_width}px")
            overflow = collect_overflow(page)
            if int(overflow["horizontalOverflowPx"]) > 0:
                errors.append(f"React Reports causes horizontal overflow at {audit_width}px")
            layout = page.locator("[data-report-workspace]").evaluate(
                """element => {
                    const primary = element.querySelector('[data-report-primary-analysis]');
                    const supporting = element.querySelector('[data-report-account-support]');
                    if (!(primary instanceof HTMLElement) || !(supporting instanceof HTMLElement)) {
                        return null;
                    }
                    const primaryRect = primary.getBoundingClientRect();
                    const supportingRect = supporting.getBoundingClientRect();
                    const workspaceRect = element.getBoundingClientRect();
                    return {
                        primaryLeft: primaryRect.left,
                        primaryRight: primaryRect.right,
                        primaryTop: primaryRect.top,
                        supportingLeft: supportingRect.left,
                        supportingRight: supportingRect.right,
                        supportingTop: supportingRect.top,
                        primaryWidth: primaryRect.width,
                        supportingWidth: supportingRect.width,
                        workspaceWidth: workspaceRect.width,
                        accountContentClipped: Array.from(
                            supporting.querySelectorAll('[aria-label]')
                        ).some(node => {
                            if (!(node instanceof HTMLElement)) return false;
                            const rect = node.getBoundingClientRect();
                            return rect.left < supportingRect.left - 1
                                || rect.right > supportingRect.right + 1;
                        }),
                    };
                }"""
            )
            if layout is None:
                errors.append("React Reports primary/supporting layout regions were not found")
            elif (
                float(layout["primaryRight"]) > float(layout["supportingLeft"])
                or abs(float(layout["primaryTop"]) - float(layout["supportingTop"])) > 2
            ):
                errors.append(
                    "React Reports does not use an aligned primary/supporting "
                    f"layout at {audit_width}px"
                )
            elif bool(layout["accountContentClipped"]):
                errors.append(f"React Reports account values are clipped at {audit_width}px")
            elif abs(float(layout["primaryWidth"]) - float(layout["supportingWidth"])) > 2:
                errors.append(
                    f"React Reports analytical pair is not evenly split at {audit_width}px"
                )
            elif (
                float(layout["supportingRight"]) - float(layout["primaryLeft"])
                < float(layout["workspaceWidth"]) * 0.95
            ):
                errors.append(
                    f"React Reports analytical pair does not use workspace width at {audit_width}px"
                )
    finally:
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("window.scrollTo(0, 0)")
    return errors


def assert_react_reports_keyboard_and_reflow(page: Page) -> list[str]:
    errors: list[str] = []
    viewport = page.viewport_size or {}
    width = int(viewport.get("width") or 0)
    height = int(viewport.get("height") or 0)
    if width > 400 or height == 0:
        return errors

    page.evaluate("document.activeElement?.blur()")
    keyboard_target_found = False
    for _ in range(40):
        page.keyboard.press("Tab")
        keyboard_target_found = bool(
            page.evaluate("document.activeElement?.matches('[data-record-identity]') ?? false")
        )
        if keyboard_target_found:
            break
    if not keyboard_target_found:
        errors.append("React Reports drill-downs are not reachable in keyboard order")
    elif not page.evaluate("document.activeElement?.matches(':focus-visible') ?? false"):
        errors.append("React Reports keyboard drill-down has no visible focus state")

    try:
        page.set_viewport_size({"width": 320, "height": height})
        page.wait_for_timeout(100)
        overflow = collect_overflow(page)
        if int(overflow["horizontalOverflowPx"]) > 0:
            errors.append("React Reports does not reflow at a 320px CSS viewport")
    finally:
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("document.activeElement?.blur(); window.scrollTo(0, 0)")
    return errors


def assert_react_reports_stress(page: Page) -> list[str]:
    errors: list[str] = []
    primary = page.locator("[data-report-primary-analysis]")
    accounts = page.locator("[data-report-account-support]")

    category_table = page.get_by_role("table", name="Поступления, расходы и итог по категориям")
    category_list = page.get_by_role("list", name="Движение денег по категориям")
    if category_table.count() == 1 and category_table.is_visible():
        category_count = category_table.locator("tbody tr").count()
    elif category_list.count() == 1 and category_list.is_visible():
        category_count = category_list.locator(":scope > li").count()
    else:
        category_count = 0
    if category_count != 24:
        errors.append(f"React Reports stress fixture hides categories: {category_count}/24")

    account_list = page.get_by_role("list", name="Остатки по счетам за период")
    account_count = account_list.locator(":scope > li").count()
    if account_count != 8:
        errors.append(f"React Reports stress fixture hides accounts: {account_count}/8")

    body_text = page.locator("body").inner_text()
    for expected_text in (
        "Жильё, коммунальные услуги и обслуживание недвижимости",
        "Расчётный счёт для ежедневных операций",
    ):
        if expected_text not in body_text:
            errors.append(f"React Reports stress fixture lost long label: {expected_text!r}")

    if page.get_by_text("Показать все", exact=True).count() != 0:
        errors.append("React Reports hides stress rows behind a show-all action")

    for region, label in ((primary, "categories"), (accounts, "accounts")):
        if region.count() != 1:
            errors.append(f"React Reports stress {label} region was not found")
            continue
        if region.evaluate("element => element.scrollWidth > element.clientWidth + 1"):
            errors.append(f"React Reports stress {label} region overflows horizontally")
    if category_table.count() == 1 and category_table.is_visible():
        clipped_cells = category_table.locator("th, td").evaluate_all(
            "cells => cells.filter(cell => cell.scrollWidth > cell.clientWidth + 1).length"
        )
        if int(clipped_cells) > 0:
            errors.append(
                f"React Reports stress table has {clipped_cells} clipped or overlapping cells"
            )
    return errors


def assert_react_account_management(page: Page) -> list[str]:
    errors: list[str] = []
    try:
        page.get_by_role("link", name="Все счета", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React account detail did not finish loading: {short_error(exc)}"]
    back_links = page.locator("a").evaluate_all(
        """
        (elements) => elements
          .filter((element) => (element.innerText || '').trim() === 'Все счета')
          .map((element) => element.getAttribute('href'))
        """
    )
    if "/app/accounts" not in back_links:
        errors.append(
            f"React account detail has no calm back link to the account directory: {back_links!r}"
        )

    trigger = page.get_by_role("button", name="Настройки счёта", exact=True)
    if trigger.count() != 1:
        return [*errors, "React account settings trigger was not found in the header"]
    trigger.click(timeout=PAGE_TIMEOUT_MS)
    dialog = page.get_by_role("dialog", name="Настройки счёта", exact=True)
    try:
        dialog.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [*errors, f"React account settings panel did not open: {short_error(exc)}"]

    for label in ("Название", "Тип", "Валюта", "Начальный баланс"):
        if dialog.get_by_label(label, exact=False).count() != 1:
            errors.append(f"React account settings field {label!r} was not found")
    if dialog.get_by_role("button", name="Сохранить изменения", exact=True).count() != 1:
        errors.append("React account settings has no explicit save action")
    if dialog.get_by_role("button", name="Перенести в архив", exact=True).count() != 1:
        errors.append("React account settings has no archive action for an active account")

    geometry = dialog.evaluate(
        """
        (element) => {
          const rect = element.getBoundingClientRect();
          return {
            left: rect.left,
            right: rect.right,
            width: rect.width,
            viewportWidth: window.innerWidth,
            documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        }
        """
    )
    if (
        float(geometry["left"]) < -1
        or float(geometry["right"]) > float(geometry["viewportWidth"]) + 1
    ):
        errors.append(f"React account settings panel escapes the viewport: {geometry!r}")
    if float(geometry["documentOverflow"]) > 1:
        errors.append("React account settings panel causes horizontal page overflow")
    dialog.get_by_role("button", name="Закрыть", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    errors.extend(assert_react_imported_operation_correction(page))
    return errors


def assert_react_imported_operation_correction(page: Page) -> list[str]:
    errors: list[str] = []

    def expose_imported_correction(route: Route) -> None:
        response = route.fetch()
        payload = response.json()
        items = payload.get("items", [])
        if not items:
            route.fulfill(response=response, json=payload)
            return
        movement = items[0]
        movement.update(
            {
                "operationType": "expense",
                "source": "bank_pdf",
                "transferRoute": None,
                "sourceTarget": {
                    "kind": "import",
                    "uploadedDocumentId": "d0f6ed6c-73db-4df0-a31d-ef46896836ae",
                    "rawTransactionId": "9e9b80bc-aeed-43f7-8f60-c85fe871410e",
                },
                "capabilities": {
                    "canEditReviewFields": True,
                    "readonlyReasonCode": None,
                },
            }
        )
        route.fulfill(response=response, json=payload)

    page.route("**/api/v1/accounts/*", expose_imported_correction)
    page.reload(wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
    trigger = page.get_by_role("button", name="Исправить", exact=True)
    if trigger.count() != 1:
        return ["React imported operation correction trigger was not found"]
    trigger.click(timeout=PAGE_TIMEOUT_MS)
    panel = page.get_by_role("region", name="Исправить операцию", exact=True)
    try:
        panel.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React imported operation correction panel did not open: {short_error(exc)}"]

    for label in ("Описание", "Категория", "Объект"):
        if panel.get_by_label(label, exact=True).count() != 1:
            errors.append(f"React imported correction field {label!r} was not found")
    description = panel.get_by_label("Описание", exact=True)
    if description.count() == 1:
        if description.evaluate("(element) => element.tagName") != "INPUT":
            errors.append(
                "React imported correction description is not a compact single-line field"
            )
        description_box = description.bounding_box()
        category_box = panel.get_by_role("combobox", name="Категория", exact=True).bounding_box()
        if (
            description_box
            and category_box
            and float(description_box["height"]) > float(category_box["height"]) + 2
        ):
            errors.append(
                "React imported correction description is taller than the shared controls"
            )
    if panel.locator("form[data-imported-operation-correction]").count() != 1:
        errors.append("React imported correction does not expose one focused inline form")
    if panel.get_by_role("link").count() != 0:
        errors.append("React imported correction repeats a non-form source action")
    category = panel.get_by_role("combobox", name="Категория", exact=True)
    if category.get_attribute("placeholder") != "Найти категорию":
        errors.append("React imported correction does not reuse searchable category selection")
    save = panel.get_by_role("button", name="Сохранить исправления", exact=True)
    cancel = panel.get_by_role("button", name="Отмена", exact=True)
    if save.count() != 1:
        errors.append("React imported correction has no explicit save action")
    if cancel.count() != 1:
        errors.append("React imported correction has no explicit cancel action")
    if save.count() == 1 and cancel.count() == 1:
        save_box = save.bounding_box()
        cancel_box = cancel.bounding_box()
        if save_box and cancel_box:
            if float(cancel_box["x"]) >= float(save_box["x"]):
                errors.append("React imported correction does not place cancel left and save right")
    movement_row = panel.locator("xpath=ancestor::article[1]")
    if movement_row.count() != 1:
        errors.append("React imported correction is not expanded inside its movement row")
    elif movement_row.get_attribute("data-state") != "working":
        errors.append("React imported correction row does not use the shared working state")

    geometry = panel.evaluate(
        """
        (element) => {
          const rect = element.getBoundingClientRect();
          return {
            left: rect.left,
            right: rect.right,
            viewportWidth: window.innerWidth,
            documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
          };
        }
        """
    )
    if (
        float(geometry["left"]) < -1
        or float(geometry["right"]) > float(geometry["viewportWidth"]) + 1
    ):
        errors.append(f"React imported correction panel escapes the viewport: {geometry!r}")
    if float(geometry["documentOverflow"]) > 1:
        errors.append("React imported correction panel causes horizontal page overflow")
    return errors


def assert_react_theme(
    page: Page,
    *,
    path: str,
    scenario_state: dict[str, str],
    theme: str,
) -> list[str]:
    errors: list[str] = []
    active_theme = page.locator("html").get_attribute("data-theme")
    if active_theme != theme:
        errors.append(f"React root theme is {active_theme!r}; expected {theme!r}")

    if path == "/app/foundation":
        preview_themes = page.locator("section[data-theme]").evaluate_all(
            "(elements) => elements.map((element) => element.dataset.theme)"
        )
        if preview_themes != list(THEMES):
            errors.append(f"foundation gallery themes are {preview_themes!r}; expected {THEMES!r}")

    if path == scenario_state.get("react_review_path"):
        if page.get_by_role("heading", name="Проверка выписки", exact=True).count() == 0:
            errors.append("React import review heading was not found")

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

    if scenario == "realistic":
        errors.extend(assert_react_manual_create(page))
        errors.extend(
            assert_react_manual_edit(
                page,
                check_conflict=int((page.viewport_size or {}).get("width") or 0) >= 1200,
            )
        )
        errors.extend(assert_react_manual_lifecycle(page))
        if int((page.viewport_size or {}).get("width") or 0) >= 1200:
            errors.extend(assert_react_manual_readonly(page, base_url=base_url))
            errors.extend(assert_react_manual_missing_session(page, base_url=base_url))

    disclosure = page.get_by_role("button", name="Показать фильтры", exact=True)
    if page.locator("#manual-ledger-search").count() == 0:
        errors.append("React manual ledger toolbar search was not found")
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
                "manual-filter-date-from",
                "manual-filter-date-to",
                "manual-filter-type",
                "manual-filter-status",
                "manual-filter-account",
                "manual-filter-category",
                "manual-filter-property",
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
        target_disclosure = page.get_by_role("button", name="Показать фильтры", exact=True)
        if target_disclosure.count() == 1:
            target_disclosure.click(timeout=PAGE_TIMEOUT_MS)
        reset = page.get_by_role("link", name="Сбросить", exact=True)
        if reset.count() == 0 or reset.get_attribute("href") != "/app/ledger/manual":
            errors.append("React manual ledger reset link leaves the React route")
        else:
            page.reload(wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
            if page.locator('article[data-state="target"]').count() != 1:
                errors.append("React manual ledger refresh lost the target row")
            filter_disclosure = page.get_by_role("button", name="Показать фильтры", exact=True)
            if filter_disclosure.count() == 1:
                filter_disclosure.click(timeout=PAGE_TIMEOUT_MS)
            reset = page.get_by_role("link", name="Сбросить", exact=True)
            reset.click(timeout=PAGE_TIMEOUT_MS)
            page.wait_for_url("**/app/ledger/manual", timeout=PAGE_TIMEOUT_MS)
            page.go_back(wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
            if "operation_id=" not in page.url:
                errors.append("React manual ledger Back did not restore route state")
            else:
                try:
                    page.locator('article[data-state="target"]').wait_for(
                        state="visible", timeout=PAGE_TIMEOUT_MS
                    )
                except PlaywrightError:
                    errors.append("React manual ledger Back did not restore the target row")
            page.go_forward(wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
            if "operation_id=" in page.url:
                errors.append("React manual ledger Forward did not restore reset state")

    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React manual ledger causes horizontal overflow")
    return errors


def assert_react_manual_readonly(page: Page, *, base_url: str) -> list[str]:
    errors: list[str] = []
    readonly_page = page.context.new_page()

    def make_ledger_readonly(route: Route) -> None:
        response = route.fetch()
        payload = response.json()
        payload["capabilities"] = {
            "canCreate": False,
            "readonlyReason": "Ручные операции доступны только для просмотра согласно вашей роли.",
        }
        for operation in payload["items"]:
            operation["capabilities"] = {
                "canEdit": False,
                "canCancel": False,
                "canRestore": False,
                "canDelete": False,
                "readonlyReason": "Операция доступна только для просмотра согласно вашей роли.",
            }
        route.fulfill(response=response, json=payload)

    readonly_page.route("**/api/v1/manual-ledger*", make_ledger_readonly)
    try:
        readonly_page.goto(
            build_url(base_url, "/app/ledger/manual"),
            wait_until="networkidle",
            timeout=PAGE_TIMEOUT_MS,
        )
        readonly_page.get_by_text(
            "Ручные операции доступны только для просмотра согласно вашей роли.",
            exact=True,
        ).wait_for(timeout=PAGE_TIMEOUT_MS)
        for action_name in (
            "Добавить операцию",
            "Исправить",
            "Отменить операцию",
            "Восстановить операцию",
            "Удалить окончательно",
        ):
            if readonly_page.get_by_role("button", name=action_name, exact=True).count() != 0:
                errors.append(f"React readonly manual ledger exposes {action_name!r}")
    except PlaywrightError as exc:
        errors.append(f"React readonly manual ledger failed: {short_error(exc)}")
    finally:
        readonly_page.close()
    return errors


def assert_react_manual_missing_session(page: Page, *, base_url: str) -> list[str]:
    browser = page.context.browser
    if browser is None:
        return ["React missing-session audit could not create an isolated browser context"]
    context = browser.new_context(viewport=page.viewport_size, locale="ru-RU")
    session_page = context.new_page()
    try:
        session_page.goto(
            build_url(base_url, "/app/ledger/manual"),
            wait_until="networkidle",
            timeout=PAGE_TIMEOUT_MS,
        )
        session_page.get_by_role("heading", name="Войдите в Booker Tee", exact=True).wait_for(
            timeout=PAGE_TIMEOUT_MS
        )
        login = session_page.get_by_role("link", name="Войти", exact=True)
        if login.get_attribute("href") != "/login?next=/app/ledger/manual":
            return ["React missing-session state has an unsafe return URL"]
    except PlaywrightError as exc:
        return [f"React missing-session state failed: {short_error(exc)}"]
    finally:
        context.close()
    return []


def assert_react_manual_create(page: Page) -> list[str]:
    errors: list[str] = []
    disclosure = page.get_by_role("button", name="Добавить операцию", exact=True)
    if disclosure.count() == 0:
        return ["React manual income/expense create disclosure was not found"]
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    form = page.locator("#manual-operation-create-panel")
    try:
        form.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React manual income/expense form did not open: {short_error(exc)}"]

    form.get_by_role("radio", name="Расход", exact=True).check()
    category = form.get_by_role("combobox", name="Категория", exact=True)
    if category.count() != 1 or category.get_attribute("placeholder") != "Найти категорию":
        errors.append("React manual form category does not use shared search")
    account = form.locator("#manual-operation-account")
    if account.locator("option").count() < 2:
        return ["React manual income/expense form has no account option"]
    account.select_option(index=1)
    amount = form.locator("#manual-operation-amount")
    description = "UI audit: React expense"
    amount.fill("0")
    form.locator("#manual-operation-description").fill(description)
    form.get_by_role("button", name="Создать расход", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    try:
        form.get_by_text("Сумма должна быть больше нуля.", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React manual income/expense 422 state was not rendered: {short_error(exc)}"]
    if amount.input_value() != "0":
        errors.append("React manual expense 422 state did not preserve the amount draft")
    if not amount.evaluate("element => element === document.activeElement"):
        errors.append("React manual expense 422 did not focus the invalid amount")

    amount.fill("123.45")
    form.get_by_role("button", name="Создать расход", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    try:
        page.get_by_role("heading", name=description, exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [
            *errors,
            f"React manual expense was not reloaded in the list: {short_error(exc)}",
        ]
    if "operation_id=" not in page.url:
        errors.append("React manual expense success did not create a stable target URL")
    if page.locator('article[data-state="target"]').count() != 1:
        errors.append("React manual expense success did not mark the created row")
    created_row = page.get_by_role("heading", name=description, exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    if "расход" not in created_row.inner_text().lower():
        errors.append("React manual expense lost its expense semantics")
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React manual expense form or result causes horizontal overflow")

    disclosure = page.get_by_role("button", name="Добавить операцию", exact=True)
    disclosure.click(timeout=PAGE_TIMEOUT_MS)
    form = page.locator("#manual-operation-create-panel")
    form.get_by_role("radio", name="Перевод", exact=True).check()
    source_account = form.locator("#manual-operation-account")
    if source_account.locator("option").count() < 3:
        return [*errors, "React manual transfer form has fewer than two accounts"]
    source_account.select_option(index=1)
    destination_account = form.locator("#manual-operation-destination-account")
    destination_account.select_option(index=1)
    transfer_description = "UI audit: React transfer"
    form.locator("#manual-operation-amount").fill("50.25")
    form.locator("#manual-operation-description").fill(transfer_description)
    form.get_by_role("button", name="Создать перевод", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    try:
        page.get_by_role("heading", name=transfer_description, exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [*errors, f"React manual transfer was not reloaded in the list: {short_error(exc)}"]
    transfer_row = page.get_by_role("heading", name=transfer_description, exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    transfer_text = transfer_row.inner_text().lower()
    if "перевод" not in transfer_text:
        errors.append("React manual transfer lost its transfer semantics")
    if "расход" in transfer_text or "доход" in transfer_text:
        errors.append("React manual transfer was presented as profit-affecting operation")
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React manual transfer form or result causes horizontal overflow")
    return errors


def assert_react_manual_edit(page: Page, *, check_conflict: bool) -> list[str]:
    errors: list[str] = []
    original_description = "UI audit: React transfer"
    updated_description = "UI audit: React transfer edited"
    heading = page.get_by_role("heading", name=original_description, exact=True)
    if heading.count() == 0:
        return ["React manual edit target was not found"]
    row = heading.locator("xpath=ancestor::article[1]")
    row.get_by_role("button", name="Исправить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    panel = page.locator('section[id^="manual-operation-edit-panel-"]')
    try:
        panel.get_by_label(re.compile(r"^Сумма")).wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React manual lazy edit did not load: {short_error(exc)}"]
    if panel.get_attribute("data-workbench-row-expansion") is None:
        errors.append("React manual edit does not use shared row expansion")
    if row.get_attribute("data-state") != "working":
        errors.append("React manual edit row does not use shared working state")

    amount = panel.get_by_label(re.compile(r"^Сумма"))
    amount.fill("0")
    panel.get_by_role("button", name="Сохранить изменения", exact=True).click(
        timeout=PAGE_TIMEOUT_MS
    )
    try:
        panel.get_by_text("Сумма должна быть больше нуля.", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React manual edit 422 state was not rendered: {short_error(exc)}"]
    if amount.input_value() != "0":
        errors.append("React manual edit 422 did not preserve the amount draft")
    if not amount.evaluate("element => element === document.activeElement"):
        errors.append("React manual edit 422 did not focus the invalid amount")

    amount.fill("50.25")
    description = panel.get_by_label("Описание")
    description.fill(updated_description)
    panel.get_by_role("button", name="Сохранить изменения", exact=True).click(
        timeout=PAGE_TIMEOUT_MS
    )
    try:
        page.get_by_role("heading", name=updated_description, exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [*errors, f"React manual edit did not reload the row: {short_error(exc)}"]
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React manual edit causes horizontal overflow")
    if check_conflict:
        errors.extend(
            assert_react_manual_edit_conflict(
                page,
                current_description=updated_description,
            )
        )
    return errors


def assert_react_manual_edit_conflict(
    page: Page,
    *,
    current_description: str,
) -> list[str]:
    row = page.get_by_role("heading", name=current_description, exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    row.get_by_role("button", name="Исправить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    panel = page.locator('section[id^="manual-operation-edit-panel-"]')
    panel.get_by_label("Описание").wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    user_draft = "UI audit: React stale draft"
    concurrent_value = "UI audit: React concurrent update"
    panel.get_by_label("Описание").fill(user_draft)

    concurrent_page = page.context.new_page()
    try:
        concurrent_page.goto(page.url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
        concurrent_row = concurrent_page.get_by_role(
            "heading",
            name=current_description,
            exact=True,
        ).locator("xpath=ancestor::article[1]")
        concurrent_row.get_by_role("button", name="Исправить", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        concurrent_panel = concurrent_page.locator('section[id^="manual-operation-edit-panel-"]')
        concurrent_panel.get_by_label("Описание").wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
        concurrent_panel.get_by_label("Описание").fill(concurrent_value)
        concurrent_panel.get_by_role(
            "button",
            name="Сохранить изменения",
            exact=True,
        ).click(timeout=PAGE_TIMEOUT_MS)
        concurrent_page.get_by_role("heading", name=concurrent_value, exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )

        panel.get_by_role("button", name="Сохранить изменения", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        try:
            panel.get_by_text("Операция уже изменилась в другом окне.", exact=True).wait_for(
                state="visible",
                timeout=PAGE_TIMEOUT_MS,
            )
        except PlaywrightError as exc:
            return [f"React manual 409 conflict was not rendered: {short_error(exc)}"]
        if panel.get_by_label("Описание").input_value() != user_draft:
            return ["React manual 409 conflict did not preserve the user draft"]
        panel.get_by_role("button", name="Загрузить актуальную версию", exact=True).click(
            timeout=PAGE_TIMEOUT_MS
        )
        page.wait_for_function(
            """
            expected => Array.from(document.querySelectorAll('input, textarea')).some(
              input => input.value === expected
            )
            """,
            arg=concurrent_value,
            timeout=PAGE_TIMEOUT_MS,
        )
    finally:
        concurrent_page.close()
    return []


def assert_react_manual_lifecycle(page: Page) -> list[str]:
    heading = page.get_by_role(
        "heading",
        name=re.compile(r"^UI audit: React (transfer edited|concurrent update)$"),
    ).first
    if heading.count() == 0:
        return ["React manual lifecycle target was not found"]
    row = heading.locator("xpath=ancestor::article[1]")
    close_edit = page.get_by_role("button", name="Закрыть", exact=True)
    if close_edit.count() == 1 and close_edit.is_visible():
        close_edit.click(timeout=PAGE_TIMEOUT_MS)

    def reveal_action(name: str):
        trigger = row.get_by_role("button", name="Ещё действия", exact=True)
        if trigger.count() == 1 and trigger.get_attribute("aria-expanded") != "true":
            trigger.click(timeout=PAGE_TIMEOUT_MS)
        return page.get_by_role("button", name=name, exact=True)

    cancel = reveal_action("Отменить операцию")
    if cancel.count() == 0:
        return ["React manual cancel action was not exposed by capability"]
    cancel.click(timeout=PAGE_TIMEOUT_MS)
    restore = row.get_by_role("button", name="Восстановить операцию", exact=True)
    refresh = page.get_by_role("button", name="Обновить строку", exact=True)
    try:
        restore.or_(refresh).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React manual cancel did not settle: {short_error(exc)}"]

    if refresh.count() == 1 and refresh.is_visible():
        if page.get_by_text("Операция уже изменилась в другом окне.", exact=True).count() == 0:
            return ["React manual lifecycle 409 did not explain the conflict"]
        refresh.click(timeout=PAGE_TIMEOUT_MS)
        refreshed_heading = page.get_by_role(
            "heading",
            name="UI audit: React concurrent update",
            exact=True,
        )
        try:
            refreshed_heading.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
        except PlaywrightError as exc:
            return [f"React manual lifecycle conflict did not refresh row: {short_error(exc)}"]
        row = refreshed_heading.locator("xpath=ancestor::article[1]")
        reveal_action("Отменить операцию").click(timeout=PAGE_TIMEOUT_MS)

    try:
        row.get_by_role("button", name="Восстановить операцию", exact=True).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
        row.get_by_text(re.compile(r"^отменено$", re.IGNORECASE)).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React manual cancel did not reconcile the row: {short_error(exc)}"]
    if row.get_by_role("button", name="Исправить", exact=True).count() != 0:
        return ["React manual cancelled row still exposes edit"]

    row.get_by_role("button", name="Восстановить операцию", exact=True).click(
        timeout=PAGE_TIMEOUT_MS
    )
    try:
        reveal_action("Отменить операцию").wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
        row.get_by_text(re.compile(r"^подтверждено$", re.IGNORECASE)).wait_for(
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError as exc:
        return [f"React manual restore did not reconcile the row: {short_error(exc)}"]

    reveal_action("Отменить операцию").click(timeout=PAGE_TIMEOUT_MS)
    try:
        delete = reveal_action("Удалить окончательно")
        delete.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React manual delete capability was not reconciled: {short_error(exc)}"]

    delete.click(timeout=PAGE_TIMEOUT_MS)
    confirmation = page.get_by_text(
        "Удалить операцию без возможности восстановления?",
        exact=False,
    )
    try:
        confirmation.wait_for(state="visible", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React manual delete confirmation was not rendered: {short_error(exc)}"]
    page.get_by_role("button", name="Не удалять", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    if row.count() != 1:
        return ["React manual delete cancellation removed the row"]

    reveal_action("Удалить окончательно").click(timeout=PAGE_TIMEOUT_MS)
    page.get_by_role("button", name="Да, удалить", exact=True).click(timeout=PAGE_TIMEOUT_MS)
    try:
        row.wait_for(state="detached", timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError as exc:
        return [f"React manual delete did not remove the row: {short_error(exc)}"]
    if "operation_id=" in page.url:
        return ["React manual delete left a stale target in the URL"]
    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        return ["React manual lifecycle actions cause horizontal overflow"]
    return []


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

          const accountRowCollisions = Array.from(
            document.querySelectorAll('tr[data-account-record]')
          ).filter(visible).flatMap((row) => {
            const balance = row.querySelector('[data-account-balance]');
            const action = row.querySelector('[data-account-action]');
            if (!balance || !action || !visible(balance) || !visible(action)) {
              return [];
            }
            const balanceRect = balance.getBoundingClientRect();
            const actionRect = action.getBoundingClientRect();
            const overlaps = !(
              balanceRect.right <= actionRect.left + 1
              || actionRect.right <= balanceRect.left + 1
              || balanceRect.bottom <= actionRect.top + 1
              || actionRect.bottom <= balanceRect.top + 1
            );
            return overlaps ? [{
              balance: textFor(balance),
              action: textFor(action),
            }] : [];
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
            accountRowCollisions,
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

    account_row_collisions = list(state.get("accountRowCollisions") or [])
    if account_row_collisions:
        examples = ", ".join(
            f"{item.get('balance')} / {item.get('action')}" for item in account_row_collisions[:3]
        )
        errors.append("designer audit: account balance overlaps its row action: " + examples)

    if path in {
        "/app/imports",
        "/app/accounts",
        "/app/categories",
        "/app/properties",
        "/categories",
        "/rules",
    }:
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


def assert_react_import_review(page: Page) -> list[str]:
    errors: list[str] = []
    if page.get_by_role("heading", name="Проверка выписки", exact=True).count() == 0:
        return ["React import review heading was not found"]
    if page.locator(".review-item, .review-row, .review-page").count() != 0:
        errors.append("React import review rendered legacy review classes")
    imports_links = page.locator('a[href="/app/imports"]').filter(has_text="Импорты")
    if imports_links.count() != 2:
        errors.append("React import review imports navigation was not found")
    else:
        for index in range(imports_links.count()):
            imports_link = imports_links.nth(index)
            if imports_link.get_attribute("href") != "/app/imports":
                errors.append("React import review imports navigation has the wrong target")
            if imports_link.get_attribute("aria-current") != "page":
                errors.append("React import review imports navigation is not active")

    all_filter = page.get_by_role("button", name=re.compile(r"^Все \d+$"))
    completed_filter = page.get_by_role("button", name=re.compile(r"^Завершённые \d+$"))
    completed_filter.click()
    try:
        page.wait_for_function(
            "() => new URLSearchParams(location.search).get('filter') === 'complete'",
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError:
        errors.append(f"React import review filter did not enter URL state: {page.url}")
    else:
        page.go_back(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        page.wait_for_function(
            "() => !new URLSearchParams(location.search).has('filter')",
            timeout=PAGE_TIMEOUT_MS,
        )
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('button[aria-pressed="true"]'))
              .some((button) => button.textContent?.trim().startsWith("Все"))
            """,
            timeout=PAGE_TIMEOUT_MS,
        )
        if all_filter.get_attribute("aria-pressed") != "true":
            errors.append("React import review Back did not restore the all filter")
        page.go_forward(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        page.wait_for_function(
            "() => new URLSearchParams(location.search).get('filter') === 'complete'",
            timeout=PAGE_TIMEOUT_MS,
        )
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('button[aria-pressed="true"]'))
              .some((button) => button.textContent?.includes("Завершённые"))
            """,
            timeout=PAGE_TIMEOUT_MS,
        )
        if completed_filter.get_attribute("aria-pressed") != "true":
            errors.append("React import review Forward did not restore the completed filter")
    all_filter.click()
    try:
        page.wait_for_function(
            "() => !new URLSearchParams(location.search).has('filter')",
            timeout=PAGE_TIMEOUT_MS,
        )
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('button[aria-pressed="true"]'))
              .some((button) => button.textContent?.trim().startsWith("Все"))
            """,
            timeout=PAGE_TIMEOUT_MS,
        )
    except PlaywrightError:
        pass
    if "filter=" in page.url:
        errors.append("React import review default filter remained in the URL")

    apply_rules = page.get_by_role("button", name="Применить правила")
    if apply_rules.count() == 0:
        errors.append("React import review apply-rules action was not found")
    else:
        apply_rules.click()
        try:
            page.get_by_text(re.compile(r"Проверено строк: \d+\.")).wait_for(
                timeout=PAGE_TIMEOUT_MS
            )
        except PlaywrightError:
            errors.append("React import review did not reconcile applied rules")

    salary_item = page.get_by_role("heading", name="Зарплата", exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    try:
        salary_item.wait_for(timeout=PAGE_TIMEOUT_MS)
    except PlaywrightError:
        return [*errors, "React import review salary row was not found"]
    classification_panel = salary_item.get_by_role(
        "button", name=re.compile(r"Выбрать категорию|Проверить предложение|Изменить")
    ).first
    if classification_panel.count() == 0:
        return [*errors, "React import review classification panel was not found"]
    classification_panel.click()
    panel = salary_item.locator("section[id^='review-panel-']")
    if panel.get_attribute("data-workbench-row-expansion") is None:
        errors.append("React import review does not use shared row expansion")
    if salary_item.get_attribute("data-state") != "working":
        errors.append("React import review row does not use shared working state")
    operation_context = panel.get_by_label("Контекст текущей операции")
    viewport = page.viewport_size
    if viewport is not None and viewport["width"] <= 720:
        if operation_context.count() == 0 or not operation_context.is_visible():
            errors.append("React import review mobile editor lost operation context")

    more_actions = salary_item.get_by_role("button", name="Ещё действия", exact=True)
    if more_actions.count() > 0:
        more_actions.focus()
        more_actions.press("Enter")
        if more_actions.get_attribute("aria-expanded") != "true":
            errors.append("React import review more-actions disclosure is not keyboard operable")
    source_action = page.get_by_role("button", name="Исходные данные")
    if source_action.count() == 0:
        errors.append("React import review technical source action was not found")
    ignore_action = page.get_by_role("button", name="Игнорировать")
    if ignore_action.count() == 0:
        errors.append("React import review lifecycle action was not found")
    else:
        ignore_action.click()
        confirmation = page.get_by_text(
            "Игнорировать строку? Она не попадёт в официальный ledger.",
            exact=True,
        )
        if confirmation.count() == 0:
            errors.append("React import review danger confirmation was not shown")
        cancel_action = page.locator("button:focus").filter(has_text="Отмена")
        if cancel_action.count() == 0:
            errors.append("React import review danger confirmation cannot be cancelled")
        else:
            if not cancel_action.evaluate("element => document.activeElement === element"):
                errors.append("React import review danger confirmation did not receive focus")
            cancel_action.click()

    category = panel.get_by_label("Категория")
    if category.count() == 0:
        errors.append("React import review category draft field was not found")
    if panel.get_by_label("Объект").count() == 0:
        errors.append("React import review property draft field was not found")
    if category.count() > 0:
        if category.get_attribute("placeholder") != "Найти категорию":
            errors.append("React import review category does not use shared search")
        category.click()
        category.fill("Прочий доход")
        category_option = page.get_by_role("option", name="Прочий доход", exact=True)
        if category_option.count() == 0:
            errors.append("React import review category search returned no option")
        else:
            category_option.click()
        confirm_action = panel.get_by_role(
            "button",
            name=re.compile(r"^Провести(?: с правилом)?$"),
        )
        try:
            confirm_action.wait_for(timeout=PAGE_TIMEOUT_MS)
        except PlaywrightError:
            errors.append("React import review confirm action was not found")
        else:
            confirm_box = confirm_action.bounding_box()
            if confirm_box is None or confirm_box["height"] < 44:
                errors.append("React import review confirm touch target is below 44px")
            rule_pattern = panel.get_by_role("textbox", name=re.compile("Автоправило"))
            if rule_pattern.count() == 0:
                errors.append("React import review auto-rule pattern field was not found")
            else:
                if rule_pattern.input_value() != "":
                    errors.append("React import review rule pattern was filled automatically")
                rule_pattern.fill("Зарплата")
                rule_preview = panel.get_by_label("Итог правила")
                if rule_preview.count() == 0 or "Зарплата" not in rule_preview.inner_text():
                    errors.append("React import review rule preview was not updated")
            confirm_action.click()
            try:
                salary_item.get_by_text(re.compile(r"^проведено$", re.IGNORECASE)).first.wait_for(
                    timeout=PAGE_TIMEOUT_MS
                )
                page.get_by_role("button", name=re.compile(r"^Завершённые \d+$")).click(
                    timeout=PAGE_TIMEOUT_MS
                )
                confirmed_salary_item = page.get_by_role(
                    "heading", name="Зарплата", exact=True
                ).locator("xpath=ancestor::article[1]")
                confirmed_salary_item.get_by_role("button", name="Ещё действия", exact=True).click(
                    timeout=PAGE_TIMEOUT_MS
                )
                page.get_by_role("button", name="Вернуть на проверку").wait_for(
                    timeout=PAGE_TIMEOUT_MS
                )
                confirmed_salary_item.get_by_role("button", name="Ещё действия", exact=True).click()
                page.get_by_role("button", name=re.compile(r"^Требуют решения \d+$")).click(
                    timeout=PAGE_TIMEOUT_MS
                )
                page.wait_for_function(
                    """
                    () => Array.from(document.querySelectorAll('button[aria-pressed="true"]'))
                      .some((button) => button.textContent?.includes("Требуют решения"))
                    """,
                    timeout=PAGE_TIMEOUT_MS,
                )
            except PlaywrightError:
                errors.append("React import review did not reconcile confirmation or expose undo")

    transfer_item = page.get_by_role("heading", name="Перевод между счетами", exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    if transfer_item.count() == 0:
        errors.append("React import review transfer row was not found")
    else:
        transfer_panel_toggle = transfer_item.get_by_role(
            "button", name=re.compile(r"Проверить перевод|Выбрать категорию|Изменить")
        ).first
        transfer_panel_toggle.click()
        transfer_panel = transfer_item.locator("section[id^='review-panel-']")
        transfer_panel.get_by_role("radio", name="Перевод").click()
        if transfer_panel.get_by_label("Второй счёт или готовая пара").count() == 0:
            errors.append("React import review transfer matching field was not found")
        if transfer_panel.get_by_role("button", name="Провести перевод").count() == 0:
            errors.append("React import review transfer action was not found")
        transfer_panel_toggle.click()

    rule_item = page.get_by_role("heading", name="OZON Маркетплейс", exact=True).locator(
        "xpath=ancestor::article[1]"
    )
    if rule_item.count() == 0:
        errors.append("React import review rule-preview row was not found")
    else:
        rule_item.get_by_role(
            "button",
            name=re.compile(r"Проверить предложение|Проверить и провести|Изменить"),
        ).first.click()
        rule_panel = rule_item.locator("section[id^='review-panel-']")
        rule_panel.get_by_role("textbox", name=re.compile("Автоправило")).fill("OZON")
        if "OZON" not in rule_panel.get_by_label("Итог правила").inner_text():
            errors.append("React import review final rule preview is not visible")

    if int(collect_overflow(page)["horizontalOverflowPx"]) > 1:
        errors.append("React import review draft panel causes horizontal overflow")
    return errors


def measure_large_import_review_queue(
    page: Page,
    *,
    row_count: int = 250,
) -> tuple[list[str], dict[str, float | int]]:
    errors: list[str] = []
    metrics: dict[str, float | int] = {}
    large_page = page.context.new_page()
    payload_bytes = 0

    def expand_review(route: Route) -> None:
        nonlocal payload_bytes
        response = route.fetch()
        payload = response.json()
        source_items = payload.get("items", [])
        if not source_items:
            route.fulfill(response=response, json=payload)
            return
        template = next(
            (item for item in source_items if not item.get("isTerminal")),
            source_items[0],
        )
        items: list[dict[str, Any]] = []
        item_ids: list[str] = []
        for index in range(row_count):
            item = deepcopy(template)
            item_id = str(UUID(f"00000000-0000-4000-8000-{10_000 + index:012x}"))
            item["id"] = item_id
            item["rowIndex"] = index + 1
            item["status"] = "needs_review"
            item["isTerminal"] = False
            item["isReviewable"] = True
            item["normalized"]["description"] = f"Измеряемая операция {index + 1}"
            item["raw"]["description"] = f"Измеряемая операция {index + 1}"
            item["ruleSuggestion"] = {
                "isActive": False,
                "wasAutoApplied": False,
                "ruleId": None,
                "ruleName": None,
                "pattern": None,
                "operationType": None,
                "categoryId": None,
                "propertyId": None,
            }
            item["posting"] = {"operationId": None, "canUndo": False}
            item["duplicateEvidence"] = None
            item["transfer"]["rawRowCandidates"] = []
            item["transfer"]["existingOperationCandidates"] = []
            items.append(item)
            item_ids.append(item_id)
        payload["items"] = items
        payload["queue"] = {
            "total": row_count,
            "completed": 0,
            "remaining": row_count,
            "firstRemainingItemId": item_ids[0],
            "orderedItemIds": item_ids,
        }
        validation = payload.get("validation")
        if validation is not None:
            validation["extractedCount"] = row_count
            validation["normalizedCount"] = row_count
            validation["needsReviewCount"] = row_count
            validation["rowProblems"] = []
        payload_bytes = len(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        route.fulfill(response=response, json=payload)

    large_page.route("**/api/v1/import-review/*", expand_review)
    started_at = time.perf_counter()
    try:
        large_page.goto(
            page.url.split("?", 1)[0],
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT_MS,
        )
        large_page.wait_for_function(
            """
            (expectedCount) =>
              document.querySelectorAll('article[id^="raw-"]').length === expectedCount
            """,
            arg=min(50, row_count),
            timeout=PAGE_TIMEOUT_MS,
        )
        initial_render_ms = (time.perf_counter() - started_at) * 1_000
        initial_dom_nodes = large_page.evaluate("() => document.getElementsByTagName('*').length")
        expanded_at = time.perf_counter()
        for expected_count in range(100, row_count + 1, 50):
            large_page.get_by_role("button", name=re.compile(r"^Показать ещё \d+$")).click()
            large_page.wait_for_function(
                """
                (expectedCount) =>
                  document.querySelectorAll('article[id^="raw-"]').length === expectedCount
                """,
                arg=min(expected_count, row_count),
                timeout=PAGE_TIMEOUT_MS,
            )
        expanded_render_ms = (time.perf_counter() - expanded_at) * 1_000
        browser_metrics = large_page.evaluate(
            """
            async () => {
              const scrollStartedAt = performance.now();
              window.scrollTo({ top: document.documentElement.scrollHeight });
              await new Promise((resolve) =>
                requestAnimationFrame(() => requestAnimationFrame(resolve))
              );
              const longTasks = performance.getEntriesByType("longtask");
              return {
                domNodes: document.getElementsByTagName("*").length,
                scrollSettleMs: performance.now() - scrollStartedAt,
                longTaskCount: longTasks.length,
                longTaskTotalMs: longTasks.reduce(
                  (total, entry) => total + entry.duration,
                  0,
                ),
              };
            }
            """
        )
        metrics = {
            "queueRows": row_count,
            "payloadBytes": payload_bytes,
            "initialVisibleRows": min(50, row_count),
            "initialRenderReadyMs": round(initial_render_ms, 1),
            "initialDomNodes": int(initial_dom_nodes),
            "expandedRenderReadyMs": round(expanded_render_ms, 1),
            "expandedDomNodes": int(browser_metrics["domNodes"]),
            "scrollSettleMs": round(float(browser_metrics["scrollSettleMs"]), 1),
            "longTaskCount": int(browser_metrics["longTaskCount"]),
            "longTaskTotalMs": round(float(browser_metrics["longTaskTotalMs"]), 1),
        }
        if int(collect_overflow(large_page)["horizontalOverflowPx"]) > 1:
            errors.append("Large React import review queue causes horizontal overflow")
    except PlaywrightError as exc:
        body_excerpt = large_page.locator("body").inner_text()[:300]
        errors.append(
            "Large React import review queue did not render: "
            f"{short_error(exc)}; page={body_excerpt!r}"
        )
    finally:
        large_page.close()
    return errors, metrics


def install_explained_reconciliation_fixture(page: Page) -> None:
    def explain_reconciliation(route: Route) -> None:
        response = route.fetch()
        payload = response.json()
        validation = payload.get("validation")
        if validation is None:
            route.fulfill(response=response, json=payload)
            return
        validation.update(
            {
                "status": "valid",
                "reasonCode": "ignored_rows_explain_mismatch",
                "currency": "RUB",
                "calculatedTotalInflow": "54807.89",
                "calculatedTotalOutflow": "71768.09",
                "ignoredTotalInflow": "50000.00",
                "ignoredTotalOutflow": "50000.00",
                "statementTotalInflow": "104807.89",
                "statementTotalOutflow": "121768.09",
                "inflowDifference": "50000.00",
                "outflowDifference": "50000.00",
                "unexplainedInflowDifference": "0.00",
                "unexplainedOutflowDifference": "0.00",
                "balanceChain": {
                    "status": "valid",
                    "direction": "ascending",
                    "checkedPairCount": 2,
                    "mismatchCount": 0,
                },
                "rowProblems": [],
            }
        )
        route.fulfill(response=response, json=payload)

    page.route("**/api/v1/import-review/*", explain_reconciliation)


def install_reports_stress_fixture(page: Page) -> None:
    category_names = (
        "Жильё, коммунальные услуги и обслуживание недвижимости с длинным названием",
        "Продажи и возвраты покупателей",
        "Проценты, кешбэк и вознаграждения",
        "Категория без движения",
        "Продукты и товары для дома",
        "Транспорт и обслуживание автомобиля",
        "Здоровье и медицинские услуги",
        "Образование и профессиональное развитие",
        "Путешествия и командировки",
        "Кафе и рестораны",
        "Подписки и цифровые сервисы",
        "Связь и интернет",
        "Налоги и обязательные платежи",
        "Подарки и помощь близким",
        "Одежда и обувь",
        "Красота и уход",
        "Домашние животные",
        "Развлечения и культура",
        "Спорт и активный отдых",
        "Ремонт и оборудование",
        "Маркетплейсы",
        "Страхование",
        "Благотворительность",
        "Прочие операции",
    )
    account_names = (
        "Расчётный счёт для ежедневных операций с особенно длинным названием",
        "Основная дебетовая карта",
        "Накопительный счёт",
        "Вклад на крупные покупки",
        "Наличные",
        "Резервный счёт",
        "Кредитная карта",
        "Архивный валютный счёт",
    )

    def money(value: Decimal) -> str:
        return format(value, ".2f")

    def category_id(index: int) -> str:
        return f"10000000-0000-4000-8000-{index:012d}"

    category_amounts: list[tuple[Decimal, Decimal]] = [
        (Decimal("9876543210.99"), Decimal("9876500000.88")),
        (Decimal("1250000.05"), Decimal("1487654.37")),
        (Decimal("7654321.10"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("0.00")),
    ]
    for index in range(4, len(category_names)):
        income = Decimal(index * 17321) if index % 3 == 0 else Decimal("0")
        expense = Decimal(index * (12345 if index % 2 == 0 else 4321)) + Decimal("0.67")
        category_amounts.append((income, expense))

    opening_balances = (
        Decimal("9876543210.99"),
        Decimal("135790.24"),
        Decimal("0.00"),
        Decimal("4200000.00"),
        Decimal("15000.00"),
        Decimal("875432.10"),
        Decimal("-245678.90"),
        Decimal("0.00"),
    )
    balance_changes = (
        Decimal("43210.11"),
        Decimal("-86420.55"),
        Decimal("1250000.05"),
        Decimal("0.00"),
        Decimal("-15000.00"),
        Decimal("98765.43"),
        Decimal("-1234.56"),
        Decimal("0.00"),
    )

    def replace_report(route: Route) -> None:
        response = route.fetch()
        payload = response.json()
        category_rows = [
            {
                "categoryId": category_id(index),
                "name": name,
                "currency": "RUB",
                "income": money(income),
                "expense": money(expense),
                "profit": money(income - expense),
                "isActive": index != len(category_names) - 1,
            }
            for index, (name, (income, expense)) in enumerate(
                zip(category_names, category_amounts, strict=True)
            )
        ]
        account_rows = []
        for index, (name, opening, change) in enumerate(
            zip(account_names, opening_balances, balance_changes, strict=True)
        ):
            account_rows.append(
                {
                    "accountId": f"20000000-0000-4000-8000-{index:012d}",
                    "name": name,
                    "currency": "RUB",
                    "openingBalance": money(opening),
                    "closingBalance": money(opening + change),
                    "balanceChange": money(change),
                    "isActive": index != len(account_names) - 1,
                }
            )

        total_income = sum((income for income, _ in category_amounts), Decimal("0"))
        total_expense = sum((expense for _, expense in category_amounts), Decimal("0"))
        total_opening = sum(opening_balances, Decimal("0"))
        total_change = sum(balance_changes, Decimal("0"))
        payload["summary"] = {
            "currency": "RUB",
            "income": money(total_income),
            "expense": money(total_expense),
            "profit": money(total_income - total_expense),
        }
        payload["balanceSummary"] = {
            "currency": "RUB",
            "openingBalance": money(total_opening),
            "closingBalance": money(total_opening + total_change),
            "balanceChange": money(total_change),
        }
        payload["categoryRows"] = category_rows
        payload["accountBalances"] = account_rows
        payload["filterOptions"]["categories"] = [
            {
                "id": row["categoryId"],
                "name": row["name"],
                "isActive": row["isActive"],
            }
            for row in category_rows
        ]
        payload["filterOptions"]["accounts"] = [
            {
                "id": row["accountId"],
                "name": row["name"],
                "currency": row["currency"],
                "isActive": row["isActive"],
            }
            for row in account_rows
        ]
        payload["uncategorized"] = {
            "items": [
                {
                    "operationId": "30000000-0000-4000-8000-000000000000",
                    "version": 1,
                    "operationDate": "2026-07-20",
                    "operationType": "expense",
                    "description": "Операция без категории для проверки действия",
                    "source": "manual",
                    "signedAmount": "-250.00",
                    "currency": "RUB",
                    "accountId": account_rows[0]["accountId"],
                    "capabilities": {
                        "canCorrect": True,
                        "readonlyReasonCode": None,
                    },
                }
            ],
            "page": 1,
            "pageSize": 10,
            "total": 1,
            "totalPages": 1,
            "hasPrevious": False,
            "hasNext": False,
        }
        route.fulfill(response=response, json=payload)

    page.route("**/api/v1/reports*", replace_report)


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
    theme: str,
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
    performance_metrics: dict[str, float | int] = {}
    error_text: str | None = None

    try:
        if scenario == "theme_audit" and path == scenario_state.get("react_review_path"):
            install_explained_reconciliation_fixture(page)
        if scenario == "reports_stress" and path == "/app/reports":
            install_reports_stress_fixture(page)
        response = page.goto(
            build_url(base_url, path),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT_MS,
        )
        page.evaluate(
            "(theme) => { document.documentElement.dataset.theme = theme; }",
            theme,
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
            theme=theme,
        )
        if scenario == "review_interactions" and path == scenario_state.get("react_review_path"):
            measurement_errors, performance_metrics = measure_large_import_review_queue(page)
            ux_assertion_errors.extend(measurement_errors)
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
        performance_metrics=performance_metrics,
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
    if scenario != "realistic" or path != "/app/ledger/manual":
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
    theme: str,
) -> list[PageAuditResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[PageAuditResult] = []
    print(f"Auditing {base_url}", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for viewport_name, width, height in VIEWPORTS:
                print(f"Viewport: {viewport_name} ({width}x{height})", flush=True)
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    locale="ru-RU",
                )
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
                    elif scenario in {
                        "review_interactions",
                        "button_audit",
                        "design_audit",
                        "theme_audit",
                    }:
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
                    if scenario_state.get("category_detail_path"):
                        dynamic_pages.append(
                            (scenario_state["category_detail_path"], "category-detail")
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
                        "theme_audit",
                    } and scenario_state.get("historical_review_path"):
                        dynamic_pages.append(
                            (
                                scenario_state["historical_review_path"],
                                "historical-import-review",
                            )
                        )
                    if scenario in {
                        "review_interactions",
                        "design_audit",
                        "theme_audit",
                    } and (scenario_state.get("react_review_path")):
                        dynamic_pages.append(
                            (
                                scenario_state["react_review_path"],
                                "react-import-review",
                            )
                        )
                    if dynamic_pages:
                        pages = (*pages, *dynamic_pages)
                    if selected_paths:
                        pages = tuple(
                            page
                            for page in pages
                            if page[0] in selected_paths or page[1] in selected_paths
                        )
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
                                    theme=theme,
                                )
                            )
                        finally:
                            page.close()
                finally:
                    context.close()
        finally:
            browser.close()
    return results


def write_report(
    results: list[PageAuditResult],
    output_dir: Path,
    *,
    scenario: str,
    theme: str,
) -> Path:
    report_path = output_dir / "report.json"
    payload = {
        "passed": all(result.passed for result in results),
        "scenario": scenario,
        "theme": theme,
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
            theme=args.theme,
        )
        report_path = write_report(
            results,
            output_dir,
            scenario=args.scenario,
            theme=args.theme,
        )
        print_summary(results, report_path)
        return 0 if all(result.passed for result in results) else 1
    finally:
        stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
