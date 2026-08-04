"""Production browser gate for Workspaces Slice 3 members and ownership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright
from ui_audit import (
    DEFAULT_AUTH_PASSWORD,
    PAGE_TIMEOUT_MS,
    start_uvicorn,
    stop_process,
    try_login,
    try_register,
)
from workspaces_slice02_browser import api_json, authenticate, page_metrics


def invitation_link(page: Page, *, base_url: str, role: str) -> str:
    page.goto(f"{base_url}/workspaces", wait_until="networkidle")
    page.locator("#workspace-invitation-create summary").click()
    page.locator("#workspace-invitation-create select[name=role]").select_option(role)
    page.locator("#workspace-invitation-create form button[type=submit]").click()
    link = page.get_by_label("Ссылка приглашения").input_value()
    return link if link.startswith("http") else f"{base_url}{link}"


def authenticate_invitee(page: Page, *, base_url: str, email: str, password: str) -> None:
    try:
        try_register(page, base_url=base_url, email=email, password=password)
    except Exception:
        try_login(page, base_url=base_url, email=email, password=password)


def accept_member(
    browser: Browser,
    owner: Page,
    *,
    base_url: str,
    password: str,
    role: str,
) -> tuple[BrowserContext, Page, str]:
    invite_url = invitation_link(owner, base_url=base_url, role=role)
    context = browser.new_context(
        reduced_motion="reduce",
        viewport={"width": 920, "height": 900},
    )
    page = context.new_page()
    email = f"workspace-slice03-{role}-{uuid4()}@example.test"
    authenticate_invitee(page, base_url=base_url, email=email, password=password)
    page.goto(invite_url, wait_until="networkidle")
    page.get_by_role("button", name="принять приглашение", exact=False).click()
    page.wait_for_load_state("networkidle")
    return context, page, email


def assert_no_clipped_buttons(page: Page, label: str) -> None:
    clipped = page.evaluate(
        """
        () => [...document.querySelectorAll('button')]
          .filter((element) => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
              rect.width > 0 && rect.height > 0 &&
              (element.scrollWidth > element.clientWidth + 1 ||
               element.scrollHeight > element.clientHeight + 1);
          })
          .map((element) => ({
            label: element.getAttribute('aria-label') || element.textContent?.trim(),
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
          }))
        """
    )
    assert clipped == [], f"{label}: clipped buttons: {clipped}"


def overflow_diagnostics(page: Page) -> list[dict[str, object]]:
    diagnostics = page.evaluate(
        """
        () => [...document.querySelectorAll('body *')]
          .map((element) => {
            const rect = element.getBoundingClientRect();
            return {
              className: typeof element.className === 'string' ? element.className : '',
              label: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 80),
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
            };
          })
          .filter((item) => item.right > document.documentElement.clientWidth + 1)
          .sort((first, second) => second.right - first.right)
          .slice(0, 12)
        """
    )
    assert isinstance(diagnostics, list)
    return diagnostics


def member_row(page: Page, email: str):
    return page.get_by_role("listitem").filter(has_text=email)


def assert_role_matrix(
    *,
    admin: Page,
    admin_email: str,
    base_url: str,
    editor: Page,
    editor_email: str,
    owner: Page,
    settings_path: str,
    viewer: Page,
    viewer_email: str,
) -> None:
    owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
    expect(owner.get_by_role("button", name="Передать владение участнику")).to_have_count(3)
    expect(owner.get_by_role("button", name="Отключить")).to_have_count(3)

    admin.goto(f"{base_url}{settings_path}", wait_until="networkidle")
    expect(admin.get_by_text(admin_email)).to_be_visible()
    expect(admin.get_by_role("button", name="Передать владение участнику")).to_have_count(0)
    expect(admin.get_by_role("button", name="Выйти")).to_have_count(1)
    expect(member_row(admin, editor_email).get_by_role("combobox")).to_be_visible()
    expect(member_row(admin, viewer_email).get_by_role("combobox")).to_be_visible()

    for page, email in ((editor, editor_email), (viewer, viewer_email)):
        page.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expect(page.get_by_text(email)).to_be_visible()
        expect(page.get_by_role("combobox")).to_have_count(0)
        expect(page.get_by_role("button", name="Передать владение участнику")).to_have_count(0)
        expect(page.get_by_role("button", name="Отключить")).to_have_count(0)
        expect(page.get_by_role("button", name="Выйти")).to_have_count(1)


def assert_forbidden_direct_mutations(
    *,
    admin: Page,
    base_url: str,
    editor: Page,
    shared_id: str,
) -> None:
    members = api_json(editor, f"/api/v1/workspaces/{shared_id}/members")["body"]
    owner_member = next(item for item in members["items"] if item["role"] == "owner")
    admin_member = next(item for item in members["items"] if item["role"] == "admin")
    workspace = api_json(editor, f"/api/v1/workspaces/{shared_id}")["body"]["workspace"]
    editor_session = api_json(editor, "/api/v1/session")["body"]
    forbidden_transfer = api_json(
        editor,
        f"/api/v1/workspaces/{shared_id}/transfer-ownership",
        {
            "body": json.dumps(
                {
                    "recipientMemberId": admin_member["id"],
                    "expectedWorkspaceUpdatedAt": workspace["updatedAt"],
                    "expectedRecipientUpdatedAt": admin_member["updatedAt"],
                }
            ),
            "headers": {
                "Content-Type": "application/json",
                "X-CSRF-Token": editor_session["csrfToken"],
            },
            "method": "POST",
        },
    )
    assert forbidden_transfer["status"] in (409, 422), forbidden_transfer

    admin_session = api_json(admin, "/api/v1/session")["body"]
    forbidden_owner_role = api_json(
        admin,
        f"/api/v1/workspaces/{shared_id}/members/{owner_member['id']}/role",
        {
            "body": json.dumps(
                {
                    "role": "viewer",
                    "expectedUpdatedAt": owner_member["updatedAt"],
                }
            ),
            "headers": {
                "Content-Type": "application/json",
                "X-CSRF-Token": admin_session["csrfToken"],
            },
            "method": "PUT",
        },
    )
    assert forbidden_owner_role["status"] == 422, forbidden_owner_role


def assert_stale_recovery(
    owner: Page,
    *,
    editor_email: str,
    shared_id: str,
) -> int:
    members = api_json(owner, f"/api/v1/workspaces/{shared_id}/members")["body"]
    editor_member = next(item for item in members["items"] if item["email"] == editor_email)
    csrf_token = api_json(owner, "/api/v1/session")["body"]["csrfToken"]
    external_update = api_json(
        owner,
        f"/api/v1/workspaces/{shared_id}/members/{editor_member['id']}/role",
        {
            "body": json.dumps(
                {
                    "role": "analyst",
                    "expectedUpdatedAt": editor_member["updatedAt"],
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
    editor_role = member_row(owner, editor_email).get_by_role("combobox")
    with owner.expect_response(
        lambda response: response.url.endswith(f"/{editor_member['id']}/role")
    ) as stale_response:
        editor_role.select_option("viewer")
    assert stale_response.value.status == 409
    expect(owner.get_by_text("Список обновлён", exact=False)).to_be_visible(timeout=PAGE_TIMEOUT_MS)
    editor_role = member_row(owner, editor_email).get_by_role("combobox")
    expect(editor_role).to_have_value("analyst")
    with owner.expect_response(
        lambda response: response.url.endswith(f"/{editor_member['id']}/role")
    ) as recovery_response:
        editor_role.select_option("editor")
    assert recovery_response.value.status == 200
    return 1


def run_flow(*, base_url: str, owner_email: str, password: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        owner_context = browser.new_context(
            reduced_motion="reduce",
            viewport={"width": 1440, "height": 1000},
        )
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
        shared_name = f"Семейное пространство {uuid4().hex[:8]}"
        owner.get_by_label("Название", exact=False).fill(shared_name)
        owner.get_by_label("Тип", exact=False).select_option("family")
        owner.get_by_role("button", name="Создать и перейти").click()
        expect(owner.get_by_text(f"Пространство «{shared_name}» создано и выбрано.")).to_be_visible(
            timeout=PAGE_TIMEOUT_MS
        )
        shared_id = owner.evaluate(
            "async () => (await (await fetch('/api/v1/session')).json()).workspace.id"
        )

        member_contexts: list[BrowserContext] = []
        admin_context, admin, admin_email = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="admin",
        )
        editor_context, editor, editor_email = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="editor",
        )
        viewer_context, viewer, viewer_email = accept_member(
            browser,
            owner,
            base_url=base_url,
            password=password,
            role="viewer",
        )
        member_contexts.extend((admin_context, editor_context, viewer_context))
        settings_path = f"/app/workspaces/{shared_id}/settings"

        assert_role_matrix(
            admin=admin,
            admin_email=admin_email,
            base_url=base_url,
            editor=editor,
            editor_email=editor_email,
            owner=owner,
            settings_path=settings_path,
            viewer=viewer,
            viewer_email=viewer_email,
        )
        assert owner.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") is True
        assert_forbidden_direct_mutations(
            admin=admin,
            base_url=base_url,
            editor=editor,
            shared_id=shared_id,
        )

        owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        expected_conflicts = assert_stale_recovery(
            owner,
            editor_email=editor_email,
            shared_id=shared_id,
        )
        console_errors[:] = [error for error in console_errors if "409 (Conflict)" not in error]

        screenshots: list[str] = []
        for viewport, width, height in (
            ("desktop", 1440, 1000),
            ("tablet", 920, 900),
            ("mobile", 390, 844),
            ("mobile-landscape", 844, 390),
        ):
            owner.set_viewport_size({"width": width, "height": height})
            owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
            expect(owner.get_by_role("heading", name="Участники")).to_be_visible()
            screenshot = f"workspace-members-{viewport}.png"
            owner.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(owner)
            assert metrics["overflowPx"] == 0, (
                f"{viewport}: {metrics}; overflow={overflow_diagnostics(owner)}"
            )
            assert metrics["undersizedTargets"] == [], f"{viewport}: {metrics}"
            assert_no_clipped_buttons(owner, viewport)

        for viewport, width, height in (
            ("text-200-desktop", 1440, 1000),
            ("text-200-mobile", 390, 844),
        ):
            owner.set_viewport_size({"width": width, "height": height})
            owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
            owner.evaluate("document.documentElement.style.fontSize = '200%'")
            screenshot = f"workspace-members-{viewport}.png"
            owner.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(owner)
            assert metrics["overflowPx"] == 0, (
                f"{viewport}: {metrics}; overflow={overflow_diagnostics(owner)}"
            )
            assert_no_clipped_buttons(owner, viewport)

        owner.set_viewport_size({"width": 1440, "height": 1000})
        owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        admin_row = owner.get_by_role("listitem").filter(has_text=admin_email)
        role_select = admin_row.get_by_role("combobox")
        role_select.focus()
        owner.keyboard.press("Tab")
        transfer_trigger = admin_row.get_by_role(
            "button", name="Передать владение участнику", exact=False
        )
        expect(transfer_trigger).to_be_focused()
        owner.keyboard.press("Enter")
        transfer_dialog = owner.get_by_role("dialog", name="Передать владение?")
        expect(transfer_dialog).to_be_visible()
        expect(transfer_dialog.get_by_role("button", name="Отмена")).to_be_focused()
        owner.keyboard.press("Escape")
        expect(transfer_trigger).to_be_focused()
        owner.keyboard.press("Tab")
        disable_trigger = admin_row.get_by_role("button", name="Отключить")
        expect(disable_trigger).to_be_focused()
        owner.keyboard.press("Enter")
        expect(owner.get_by_role("dialog", name="Отключить участника?")).to_be_visible()
        owner.keyboard.press("Escape")
        expect(disable_trigger).to_be_focused()

        transfer_trigger.focus()
        owner.keyboard.press("Enter")
        transfer_dialog.get_by_role("button", name="Передать владение").focus()
        owner.keyboard.press("Enter")
        owner.wait_for_load_state("networkidle")
        expect(owner.get_by_text("Владение пространством передано", exact=False)).to_be_visible()
        leave_trigger = owner.get_by_role("button", name="Выйти")
        leave_trigger.focus()
        owner.keyboard.press("Enter")
        leave_dialog = owner.get_by_role("dialog", name="Выйти из пространства?")
        expect(leave_dialog).to_be_visible()
        expect(leave_dialog.get_by_role("button", name="Отмена")).to_be_focused()
        leave_dialog.get_by_role("button", name="Выйти из пространства").focus()
        owner.keyboard.press("Enter")
        owner.wait_for_load_state("networkidle")
        expect(owner.get_by_role("heading", name="Рабочие пространства")).to_be_visible()
        expect(owner.get_by_text("Вы вышли из рабочего пространства.")).to_be_visible()

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "sharedWorkspaceId": shared_id,
                    "memberEmails": {
                        "admin": admin_email,
                        "editor": editor_email,
                        "viewer": viewer_email,
                    },
                    "screenshots": screenshots,
                    "keyboardFlow": True,
                    "reducedMotion": True,
                    "roleMatrix": ["owner", "admin", "editor", "viewer"],
                    "staleMemberRecovery": True,
                    "expectedConflictResponses": expected_conflicts,
                    "forbiddenDirectMutations": True,
                    "textZoom": "200%",
                    "ownershipTransferred": True,
                    "formerOwnerLeft": True,
                    "consoleErrors": console_errors,
                    "pageErrors": page_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        for context in member_contexts:
            context.close()
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
        default=Path("/tmp/booker-workspaces-slice03-browser"),
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
    print(f"Workspaces Slice 3 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
