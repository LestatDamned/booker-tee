"""Production browser gate for Workspaces Slice 2 settings and stale recovery."""

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


def api_json(page: Page, path: str, options: dict[str, object] | None = None):
    result = page.evaluate(
        """
        async ({path, options}) => {
          const response = await fetch(path, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json', ...(options?.headers || {}) },
            ...options,
          });
          return { body: await response.json(), status: response.status };
        }
        """,
        {"options": options or {}, "path": path},
    )
    assert isinstance(result, dict)
    return result


def page_metrics(page: Page) -> dict[str, object]:
    metrics = page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const targets = [...document.querySelectorAll(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled])'
          )].filter((element) => {
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
                label: element.getAttribute('aria-label') ||
                  element.getAttribute('name') || element.textContent?.trim(),
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


def save_settings(
    page: Page,
    *,
    currency: str,
    name: str,
    workspace_type: str,
) -> None:
    page.get_by_label("Название", exact=False).fill(name)
    page.get_by_label("Тип", exact=False).select_option(workspace_type)
    page.get_by_label("Основная валюта", exact=False).select_option(currency)
    page.get_by_role("button", name="Сохранить").click()
    expect(page.get_by_text("Настройки пространства сохранены.")).to_be_visible(
        timeout=PAGE_TIMEOUT_MS
    )


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
        console_errors.clear()
        page_errors.clear()

        session_result = api_json(page, "/api/v1/session")
        assert session_result["status"] == 200
        session = session_result["body"]
        personal_id = session["workspace"]["id"]
        csrf_token = session["csrfToken"]
        personal_path = f"/app/workspaces/{personal_id}/settings"

        page.goto(f"{base_url}{personal_path}", wait_until="networkidle")
        expect(page.get_by_role("heading", name="Основные данные")).to_be_visible()
        expect(page.get_by_text("Ранее сохранённые данные не изменятся")).to_be_visible()
        personal_name = "Личный финансовый контекст — долгосрочное планирование"
        save_settings(
            page,
            currency="EUR",
            name=personal_name,
            workspace_type="personal",
        )
        session_after_save = api_json(page, "/api/v1/session")["body"]
        assert session_after_save["workspace"]["name"] == personal_name
        expect(page.get_by_text(personal_name).first).to_be_visible()

        stale_snapshot = api_json(page, f"/api/v1/workspaces/{personal_id}")["body"]
        external_name = "Версия из другой вкладки"
        external_update = api_json(
            page,
            f"/api/v1/workspaces/{personal_id}",
            {
                "body": json.dumps(
                    {
                        "defaultCurrency": "EUR",
                        "expectedUpdatedAt": stale_snapshot["workspace"]["updatedAt"],
                        "name": external_name,
                        "workspaceType": "personal",
                    }
                ),
                "headers": {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrf_token,
                },
                "method": "PUT",
            },
        )
        assert external_update["status"] == 200, external_update
        retry_name = "Повторное изменение после конфликта"
        page.get_by_label("Название", exact=False).fill(retry_name)
        page.get_by_role("button", name="Сохранить").click()
        expect(page.get_by_text("Настройки изменились в другой вкладке")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )
        expected_conflict_errors = [error for error in console_errors if "409 (Conflict)" in error]
        assert len(expected_conflict_errors) == 1, console_errors
        console_errors[:] = [error for error in console_errors if "409 (Conflict)" not in error]
        expect(page.get_by_label("Название", exact=False)).to_have_value(external_name)
        expect(page.get_by_text("Повторите нужное изменение", exact=False)).to_be_visible()
        page.get_by_label("Название", exact=False).fill(retry_name)
        page.get_by_role("button", name="Сохранить").click()
        expect(page.get_by_text("Настройки пространства сохранены.")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )

        page.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        page.get_by_role("button", name="Новое пространство").click()
        shared_name = "Семейный бюджет — квартира, поездки и общие расходы"
        page.get_by_label("Название", exact=False).fill(shared_name)
        page.get_by_label("Тип", exact=False).select_option("family")
        page.get_by_label("Основная валюта", exact=False).select_option("USD")
        page.get_by_role("button", name="Создать и перейти").click()
        expect(page.get_by_text(f"Пространство «{shared_name}» создано и выбрано.")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )
        shared_session = api_json(page, "/api/v1/session")["body"]
        shared_id = shared_session["workspace"]["id"]
        shared_path = f"/app/workspaces/{shared_id}/settings"
        page.goto(f"{base_url}{shared_path}", wait_until="networkidle")
        expect(page.get_by_label("Тип", exact=False)).to_have_value("family")
        expect(page.get_by_text("Активные сессии")).to_be_visible()

        screenshots: list[str] = []
        for viewport, width, height in (
            ("desktop", 1440, 1000),
            ("tablet", 920, 900),
            ("mobile", 390, 844),
        ):
            page.set_viewport_size({"width": width, "height": height})
            page.goto(f"{base_url}{shared_path}", wait_until="networkidle")
            screenshot = f"workspace-settings-{viewport}.png"
            page.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(page)
            assert metrics["overflowPx"] == 0, f"{viewport}: {metrics}"
            assert metrics["undersizedTargets"] == [], f"{viewport}: {metrics}"

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "personalWorkspaceId": personal_id,
                    "sharedWorkspaceId": shared_id,
                    "staleSnapshotReloaded": True,
                    "expectedConflictResponses": len(expected_conflict_errors),
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
        default=Path("/tmp/booker-workspaces-slice02-browser"),
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
    print(f"Workspaces Slice 2 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
