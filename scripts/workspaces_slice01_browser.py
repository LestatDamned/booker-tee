"""Production browser gate for Workspaces Slice 1 create and switch boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright
from ui_audit import (
    DEFAULT_AUTH_PASSWORD,
    PAGE_TIMEOUT_MS,
    start_uvicorn,
    stop_process,
    try_login,
    try_register,
)


def authenticate(page: Page, *, base_url: str, email: str, password: str) -> None:
    try:
        try_register(page, base_url=base_url, email=email, password=password)
    except Exception:
        try_login(page, base_url=base_url, email=email, password=password)


def session_snapshot(page: Page) -> dict[str, object]:
    snapshot = page.evaluate(
        """
        async () => {
          const response = await fetch('/api/v1/session', {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
          });
          if (!response.ok) throw new Error(`session HTTP ${response.status}`);
          return response.json();
        }
        """
    )
    assert isinstance(snapshot, dict)
    return snapshot


def page_metrics(page: Page) -> dict[str, object]:
    metrics = page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const targets = [...document.querySelectorAll('a[href], button:not([disabled])')]
            .filter((element) => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return style.display !== 'none' && style.visibility !== 'hidden' &&
                rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight;
            });
          return {
            overflowPx: Math.max(0, root.scrollWidth - root.clientWidth),
            undersizedTargets: targets.map((element) => {
              const rect = element.getBoundingClientRect();
              return {
                label: element.getAttribute('aria-label') || element.textContent?.trim(),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
              };
            }).filter((target) => target.width < 44 || target.height < 44),
          };
        }
        """
    )
    assert isinstance(metrics, dict)
    return metrics


def run_flow(*, base_url: str, email: str, password: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        authenticate(page, base_url=base_url, email=email, password=password)
        # A duplicate fixed audit identity intentionally falls back from signup
        # (400) to login; only errors from the production flow count below.
        console_errors.clear()
        page_errors.clear()

        page.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        initial = session_snapshot(page)
        initial_workspace = initial["workspace"]
        assert isinstance(initial_workspace, dict)
        initial_id = str(initial_workspace["id"])
        initial_name = str(initial_workspace["name"])

        page.get_by_role("button", name="Новое пространство").click()
        expect(page.get_by_label("Название", exact=False)).to_be_focused()
        page.get_by_label("Название", exact=False).fill("Семейный бюджет Slice 1")
        page.get_by_label("Тип", exact=False).select_option("family")
        page.get_by_label("Основная валюта", exact=False).select_option("USD")
        page.get_by_role("button", name="Создать и перейти").click()
        expect(
            page.get_by_text("Пространство «Семейный бюджет Slice 1» создано и выбрано.")
        ).to_be_visible(timeout=PAGE_TIMEOUT_MS)

        created = session_snapshot(page)
        created_workspace = created["workspace"]
        assert isinstance(created_workspace, dict)
        created_id = str(created_workspace["id"])
        assert created_id != initial_id
        assert created_workspace["name"] == "Семейный бюджет Slice 1"
        assert created_workspace["defaultCurrency"] == "USD"

        cross_feature_routes = (
            ("/app/accounts", "Счета"),
            ("/app/imports", "Импорты"),
            ("/app/ledger/manual", "Ручные операции"),
            ("/app/reports", "Отчёты"),
            ("/app/rules", "Правила операций"),
        )
        verified_routes: list[str] = []
        for path, heading in cross_feature_routes:
            page.goto(f"{base_url}{path}", wait_until="networkidle")
            expect(page.get_by_role("heading", name=heading)).to_be_visible()
            feature_session = session_snapshot(page)
            assert isinstance(feature_session["workspace"], dict)
            assert feature_session["workspace"]["id"] == created_id
            verified_routes.append(path)

        page.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        page.get_by_role(
            "button",
            name=f"Выбрать пространство «{initial_name}»",
            exact=True,
        ).click()
        expect(page.get_by_text(f"Текущее пространство: «{initial_name}».")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )
        restored = session_snapshot(page)
        assert isinstance(restored["workspace"], dict)
        assert restored["workspace"]["id"] == initial_id

        screenshots: list[str] = []
        for name, width, height in (
            ("desktop", 1440, 1000),
            ("tablet", 920, 900),
            ("mobile", 390, 844),
        ):
            page.set_viewport_size({"width": width, "height": height})
            page.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
            screenshot = f"workspaces-{name}.png"
            page.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(page)
            assert metrics["overflowPx"] == 0, f"{name}: {metrics}"
            assert metrics["undersizedTargets"] == [], f"{name}: {metrics}"

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "initialWorkspaceId": initial_id,
                    "createdWorkspaceId": created_id,
                    "restoredWorkspaceId": restored["workspace"]["id"],
                    "verifiedRoutes": verified_routes,
                    "screenshots": screenshots,
                    "consoleErrors": console_errors,
                    "pageErrors": page_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        context.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--auth-email", required=True)
    parser.add_argument("--auth-password", default=DEFAULT_AUTH_PASSWORD)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/booker-workspaces-slice01-browser"),
    )
    args = parser.parse_args()
    process = None
    base_url = args.base_url
    try:
        if base_url is None:
            base_url, process = start_uvicorn(20)
        run_flow(
            base_url=base_url,
            email=args.auth_email,
            password=args.auth_password,
            output_dir=args.output_dir,
        )
    finally:
        stop_process(process)
    print(f"Workspaces Slice 1 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
