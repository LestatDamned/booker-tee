"""Production browser gate for Workspaces Slice 3 members and ownership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright
from ui_audit import (
    DEFAULT_AUTH_PASSWORD,
    PAGE_TIMEOUT_MS,
    start_uvicorn,
    stop_process,
    try_login,
    try_register,
)
from workspaces_slice02_browser import authenticate, page_metrics


def invitation_link(page: Page, *, base_url: str) -> str:
    page.goto(f"{base_url}/workspaces", wait_until="networkidle")
    page.locator("#workspace-invitation-create summary").click()
    page.locator("#workspace-invitation-create select[name=role]").select_option("editor")
    page.locator("#workspace-invitation-create form button[type=submit]").click()
    link = page.get_by_label("Ссылка приглашения").input_value()
    return link if link.startswith("http") else f"{base_url}{link}"


def authenticate_invitee(page: Page, *, base_url: str, email: str, password: str) -> None:
    try:
        try_register(page, base_url=base_url, email=email, password=password)
    except Exception:
        try_login(page, base_url=base_url, email=email, password=password)


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
        invite_url = invitation_link(owner, base_url=base_url)

        invitee_context = browser.new_context(viewport={"width": 920, "height": 900})
        invitee = invitee_context.new_page()
        invitee_email = f"workspace-slice03-invitee-{uuid4()}@example.test"
        authenticate_invitee(
            invitee,
            base_url=base_url,
            email=invitee_email,
            password=password,
        )
        invitee.goto(invite_url, wait_until="networkidle")
        invitee.get_by_role("button", name="принять приглашение", exact=False).click()
        invitee.wait_for_load_state("networkidle")

        settings_path = f"/app/workspaces/{shared_id}/settings"
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
            expect(owner.get_by_text(invitee_email)).to_be_visible()
            screenshot = f"workspace-members-{viewport}.png"
            owner.screenshot(path=output_dir / screenshot, full_page=True)
            screenshots.append(screenshot)
            metrics = page_metrics(owner)
            assert metrics["overflowPx"] == 0, f"{viewport}: {metrics}"
            assert metrics["undersizedTargets"] == [], f"{viewport}: {metrics}"

        owner.set_viewport_size({"width": 1440, "height": 1000})
        owner.goto(f"{base_url}{settings_path}", wait_until="networkidle")
        owner.get_by_role("button", name="Передать владение участнику", exact=False).click()
        dialog = owner.get_by_role("dialog", name="Передать владение?")
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Передать владение").click()
        owner.wait_for_load_state("networkidle")
        expect(owner.get_by_text("Владение пространством передано", exact=False)).to_be_visible()
        owner.get_by_role("button", name="Выйти").click()
        expect(owner.get_by_role("dialog", name="Выйти из пространства?")).to_be_visible()
        owner.get_by_role("button", name="Выйти из пространства").click()
        owner.wait_for_load_state("networkidle")
        expect(owner.get_by_role("heading", name="Рабочие пространства")).to_be_visible()
        expect(owner.get_by_text("Вы вышли из рабочего пространства.")).to_be_visible()

        assert console_errors == [], console_errors
        assert page_errors == [], page_errors
        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "sharedWorkspaceId": shared_id,
                    "memberEmail": invitee_email,
                    "screenshots": screenshots,
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
        invitee_context.close()
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
