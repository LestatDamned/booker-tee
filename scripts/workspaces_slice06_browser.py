"""Production browser gate for Workspaces Slice 6 lifecycle boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright
from ui_audit import DEFAULT_AUTH_PASSWORD, PAGE_TIMEOUT_MS, start_uvicorn, stop_process
from workspaces_slice02_browser import api_json, authenticate, page_metrics
from workspaces_slice03_browser import accept_member, assert_no_clipped_buttons
from workspaces_slice04_browser import create_invitation


def click_lifecycle(page: Page, action: str, confirm: str) -> None:
    page.get_by_role("button", name=action, exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name=confirm, exact=True).click()
    page.wait_for_url("**/app/workspaces", timeout=PAGE_TIMEOUT_MS)


def run_flow(*, base_url: str, owner_email: str, password: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        owner_context = browser.new_context(viewport={"width": 1440, "height": 1000})
        owner = owner_context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        owner.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        owner.on("pageerror", lambda error: page_errors.append(str(error)))
        authenticate(owner, base_url=base_url, email=owner_email, password=password)
        fallback_id = api_json(owner, "/api/v1/session")["body"]["workspace"]["id"]

        owner.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        owner.screenshot(path=output_dir / "workspace-directory-start.png", full_page=True)
        expect(owner.get_by_role("heading", name="Рабочие пространства")).to_be_visible()
        owner.get_by_role("button", name="Новое пространство").click()
        workspace_name = f"Lifecycle {uuid4().hex[:8]}"
        owner.get_by_label("Название", exact=False).fill(workspace_name)
        owner.get_by_label("Тип", exact=False).select_option("family")
        owner.get_by_role("button", name="Создать и перейти").click()
        expect(
            owner.get_by_text(f"Пространство «{workspace_name}» создано и выбрано.")
        ).to_be_visible(timeout=PAGE_TIMEOUT_MS)
        workspace_id = api_json(owner, "/api/v1/session")["body"]["workspace"]["id"]
        settings_url = f"{base_url}/app/workspaces/{workspace_id}/settings"

        viewer_context, viewer, _ = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="viewer",
        )
        viewer.goto(settings_url, wait_until="networkidle")
        expect(viewer.get_by_role("button", name="Деактивировать")).to_have_count(0)

        owner.goto(settings_url, wait_until="networkidle")
        create_invitation(owner, role="editor")
        owner.get_by_role("button", name="Закрыть").click()

        screenshots: list[str] = []
        for viewport, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            owner.set_viewport_size({"width": width, "height": height})
            owner.goto(settings_url, wait_until="networkidle")
            screenshot = f"workspace-lifecycle-{viewport}.png"
            owner.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(owner)
            assert metrics["overflowPx"] == 0, f"{viewport}: {metrics}"
            assert metrics["undersizedTargets"] == [], f"{viewport}: {metrics}"
            assert_no_clipped_buttons(owner, viewport)

        owner.set_viewport_size({"width": 1440, "height": 1000})
        owner.goto(settings_url, wait_until="networkidle")
        trigger = owner.get_by_role("button", name="Деактивировать", exact=True)
        trigger.focus()
        owner.keyboard.press("Enter")
        expect(owner.get_by_role("button", name="Отмена")).to_be_focused()
        owner.keyboard.press("Escape")
        expect(trigger).to_be_focused()

        stale = api_json(owner, f"/api/v1/workspaces/{workspace_id}")["body"]
        session = api_json(owner, "/api/v1/session")["body"]
        update = api_json(
            owner,
            f"/api/v1/workspaces/{workspace_id}",
            {
                "body": json.dumps(
                    {
                        "name": f"{workspace_name} external",
                        "workspaceType": "family",
                        "defaultCurrency": "RUB",
                        "expectedUpdatedAt": stale["workspace"]["updatedAt"],
                    }
                ),
                "headers": {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrfToken"],
                },
                "method": "PUT",
            },
        )
        assert update["status"] == 200
        owner.get_by_role("button", name="Деактивировать", exact=True).click()
        owner.get_by_role("button", name="Да, деактивировать", exact=True).click()
        expect(owner.get_by_text("Настройки изменились в другой вкладке")).to_be_visible()
        console_errors[:] = [error for error in console_errors if "409 (Conflict)" not in error]

        click_lifecycle(owner, "Деактивировать", "Да, деактивировать")
        owner_session = api_json(owner, "/api/v1/session")["body"]
        viewer_session = api_json(viewer, "/api/v1/session")["body"]
        assert owner_session["workspace"]["id"] == fallback_id
        assert viewer_session["workspace"]["id"] != workspace_id
        owner.goto(settings_url, wait_until="networkidle")
        expect(owner.get_by_text("Неактивно", exact=True)).to_be_visible()
        click_lifecycle(owner, "Восстановить", "Восстановить пространство")
        assert api_json(owner, "/api/v1/session")["body"]["workspace"]["id"] == fallback_id
        directory = api_json(owner, "/api/v1/workspaces")["body"]
        restored = next(item for item in directory["items"] if item["id"] == workspace_id)
        assert restored["isActive"] is True
        assert restored["isCurrent"] is False
        invitation_list = api_json(owner, f"/api/v1/workspaces/{workspace_id}/invitations")
        assert invitation_list["status"] == 200
        assert invitation_list["body"]["items"] == []

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "workspaceId": workspace_id,
                    "ownerFallbackId": fallback_id,
                    "roleMatrix": ["owner", "viewer"],
                    "staleConflictRecovery": True,
                    "pendingInvitationsRevoked": True,
                    "sessionsMoved": True,
                    "restoreDidNotSwitchSessionBack": True,
                    "keyboardDialogFocus": True,
                    "screenshots": screenshots,
                    "consoleErrors": console_errors,
                    "pageErrors": page_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        viewer_context.close()
        owner_context.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--auth-email", required=True)
    parser.add_argument("--auth-password", default=DEFAULT_AUTH_PASSWORD)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/booker-workspaces-slice06-browser"),
    )
    args = parser.parse_args()
    process = None
    base_url = args.base_url
    try:
        if base_url is None:
            base_url, process = start_uvicorn(20)
        run_flow(
            base_url=base_url,
            owner_email=args.auth_email,
            password=args.auth_password,
            output_dir=args.output_dir,
        )
    finally:
        stop_process(process)
    print(f"Workspaces Slice 6 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
