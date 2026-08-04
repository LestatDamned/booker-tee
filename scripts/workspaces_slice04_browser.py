from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright
from ui_audit import DEFAULT_AUTH_PASSWORD, PAGE_TIMEOUT_MS, start_uvicorn, stop_process
from workspaces_slice02_browser import api_json, authenticate, page_metrics
from workspaces_slice03_browser import accept_member, assert_no_clipped_buttons


def create_invitation(page: Page, *, role: str) -> str:
    section = page.get_by_role("heading", name="Приглашения", exact=True).locator(
        "xpath=ancestor::section[1]"
    )
    section.locator("select").select_option(role)
    with page.expect_response(
        lambda response: response.url.endswith("/invitations") and response.request.method == "POST"
    ) as response_info:
        section.get_by_role("button", name="Создать ссылку").click()
    assert response_info.value.status == 201
    assert response_info.value.headers.get("cache-control") == "no-store"
    share = section.get_by_label("Ссылка приглашения").input_value()
    assert share
    return share


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
        owner.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        owner.get_by_role("button", name="Новое пространство").click()
        shared_name = f"Приглашения {uuid4().hex[:8]}"
        owner.get_by_label("Название", exact=False).fill(shared_name)
        owner.get_by_label("Тип", exact=False).select_option("family")
        owner.get_by_role("button", name="Создать и перейти").click()
        expect(owner.get_by_text(f"Пространство «{shared_name}» создано и выбрано.")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )
        shared_id = owner.evaluate(
            "async () => (await (await fetch('/api/v1/session')).json()).workspace.id"
        )
        settings_path = f"/app/workspaces/{shared_id}/settings"

        admin_context, admin, admin_email = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="admin",
        )
        viewer_context, viewer, viewer_email = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="viewer",
        )

        owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expect(owner.get_by_role("heading", name="Приглашения", exact=True)).to_be_visible()
        share_url = create_invitation(owner, role="editor")
        token = share_url.rsplit("/", 1)[-1]
        invitation_list = api_json(
            owner,
            f"/api/v1/workspaces/{shared_id}/invitations",
        )
        assert invitation_list["status"] == 200
        serialized_list = json.dumps(invitation_list["body"])
        assert token not in serialized_list
        assert "tokenHash" not in serialized_list

        public_context = browser.new_context()
        public_page = public_context.new_page()
        public_response = public_page.goto(share_url, wait_until="networkidle")
        assert public_response is not None
        assert public_response.headers.get("cache-control") == "no-store"
        assert public_response.headers.get("referrer-policy") == "no-referrer"
        expect(public_page.get_by_text(shared_name)).to_be_visible()
        expect(public_page.get_by_text("Редактор")).to_be_visible()
        public_context.close()

        owner.reload(wait_until="networkidle")
        expect(owner.get_by_label("Ссылка приглашения")).to_have_count(0)
        expect(owner.get_by_role("button", name="Отозвать")).to_have_count(1)
        stale_invitation = invitation_list["body"]["items"][0]
        session = api_json(owner, "/api/v1/session")["body"]
        external_revoke = api_json(
            owner,
            f"/api/v1/workspaces/{shared_id}/invitations/{stale_invitation['id']}/revoke",
            {
                "body": json.dumps({"expectedUpdatedAt": stale_invitation["updatedAt"]}),
                "headers": {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrfToken"],
                },
                "method": "POST",
            },
        )
        assert external_revoke["status"] == 200
        owner.get_by_role("button", name="Отозвать").click()
        owner.get_by_role("button", name="Отозвать приглашение").click()
        expect(owner.get_by_text("Список приглашений обновлён", exact=False)).to_be_visible()
        expect(owner.get_by_text("Ожидающих приглашений нет.")).to_be_visible()
        console_errors[:] = [error for error in console_errors if "409 (Conflict)" not in error]

        admin.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expect(admin.get_by_text(admin_email)).to_be_visible()
        invitation_section = admin.get_by_role("heading", name="Приглашения", exact=True).locator(
            "xpath=ancestor::section[1]"
        )
        admin_roles = invitation_section.locator("select option").all_text_contents()
        assert "Администратор" not in admin_roles
        assert admin_roles == [
            "Редактор",
            "Наблюдатель",
            "Загрузка данных",
            "Аналитик",
        ]
        admin_share_url = create_invitation(admin, role="viewer")
        admin.get_by_role("button", name="Закрыть").click()

        viewer.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expect(viewer.get_by_text(viewer_email)).to_be_visible()
        expect(viewer.get_by_role("button", name="Создать ссылку")).to_have_count(0)
        expect(viewer.get_by_role("button", name="Отозвать")).to_have_count(0)
        viewer_list = api_json(
            viewer,
            f"/api/v1/workspaces/{shared_id}/invitations",
        )
        assert viewer_list["status"] == 200
        assert viewer_list["body"]["items"] == []
        assert viewer_list["body"]["capabilities"]["canCreate"] is False

        owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expect(owner.get_by_role("button", name="Отозвать")).to_have_count(1)
        screenshots: list[str] = []
        for viewport, width, height in (
            ("desktop", 1440, 1000),
            ("tablet", 920, 900),
            ("mobile", 390, 844),
            ("mobile-landscape", 844, 390),
        ):
            owner.set_viewport_size({"width": width, "height": height})
            owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
            screenshot = f"workspace-invitations-{viewport}.png"
            owner.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(owner)
            assert metrics["overflowPx"] == 0, f"{viewport}: {metrics}"
            assert metrics["undersizedTargets"] == [], f"{viewport}: {metrics}"
            assert_no_clipped_buttons(owner, viewport)

        revoke_trigger = owner.get_by_role("button", name="Отозвать")
        revoke_trigger.focus()
        owner.keyboard.press("Enter")
        dialog = owner.get_by_role("dialog", name="Отозвать приглашение?")
        expect(dialog.get_by_role("button", name="Отмена")).to_be_focused()
        owner.keyboard.press("Escape")
        expect(revoke_trigger).to_be_focused()
        owner.keyboard.press("Enter")
        dialog.get_by_role("button", name="Отозвать приглашение").focus()
        owner.keyboard.press("Enter")
        expect(owner.get_by_text("Ожидающих приглашений нет.")).to_be_visible()

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "sharedWorkspaceId": shared_id,
                    "memberEmails": {"admin": admin_email, "viewer": viewer_email},
                    "screenshots": screenshots,
                    "credentialHiddenAfterReload": True,
                    "credentialAbsentFromList": True,
                    "publicPreviewNoStore": True,
                    "staleRevokeRecovery": True,
                    "roleMatrix": ["owner", "admin", "viewer"],
                    "keyboardRevoke": True,
                    "adminShareUrlCreated": bool(admin_share_url),
                    "consoleErrors": console_errors,
                    "pageErrors": page_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        admin_context.close()
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
        default=Path("/tmp/booker-workspaces-slice04-browser"),
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
    print(f"Workspaces Slice 4 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
