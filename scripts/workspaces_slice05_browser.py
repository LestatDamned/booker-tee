from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright
from ui_audit import (
    DEFAULT_AUTH_PASSWORD,
    PAGE_TIMEOUT_MS,
    start_uvicorn,
    stop_process,
    try_register,
)
from workspaces_slice02_browser import api_json, authenticate, page_metrics
from workspaces_slice04_browser import create_invitation

UNAVAILABLE = "Приглашение не найдено или уже недействительно."


def accept(page: Page, *, expected_role: str, invite_url: str) -> str:
    page.goto(invite_url, wait_until="networkidle")
    page.get_by_role("button", name="принять приглашение", exact=False).click()
    page.wait_for_url("**/app/workspaces", timeout=PAGE_TIMEOUT_MS)
    session = api_json(page, "/api/v1/session")["body"]
    assert session["membership"]["role"] == expected_role
    return session["workspace"]["id"]


def register_from_invitation(
    page: Page,
    *,
    email: str,
    invite_url: str,
    password: str,
) -> None:
    page.goto(invite_url, wait_until="networkidle")
    page.get_by_role("main").get_by_role("link", name="регистрация", exact=False).click()
    assert urlparse(page.url).path == "/signup", page.url
    assert parse_qs(urlparse(page.url).query)["next"] == [urlparse(invite_url).path]
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="name"]').fill("Invitation signup")
    page.locator('input[name="password"]').fill(password)
    page.locator('button[type="submit"]').click()
    page.wait_for_url(invite_url, timeout=PAGE_TIMEOUT_MS)


def login_from_invitation(
    page: Page,
    *,
    email: str,
    invite_url: str,
    password: str,
) -> None:
    page.goto(invite_url, wait_until="networkidle")
    page.get_by_role("main").get_by_role("link", name="войти", exact=False).click()
    assert urlparse(page.url).path == "/login", page.url
    assert parse_qs(urlparse(page.url).query)["next"] == [urlparse(invite_url).path]
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('button[type="submit"]').click()
    page.wait_for_url(invite_url, timeout=PAGE_TIMEOUT_MS)


def run_flow(*, base_url: str, owner_email: str, password: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        owner_context = browser.new_context(viewport={"width": 1440, "height": 1000})
        owner = owner_context.new_page()
        authenticate(owner, base_url=base_url, email=owner_email, password=password)
        owner.goto(f"{base_url}/app/workspaces", wait_until="networkidle")
        owner.get_by_role("button", name="Новое пространство").click()
        shared_name = f"Приём приглашений {uuid4().hex[:8]}"
        owner.get_by_label("Название", exact=False).fill(shared_name)
        owner.get_by_label("Тип", exact=False).select_option("family")
        owner.get_by_role("button", name="Создать и перейти").click()
        expect(
            owner.get_by_text(f"Пространство «{shared_name}» создано и выбрано.")
        ).to_be_visible()
        shared_id = api_json(owner, "/api/v1/session")["body"]["workspace"]["id"]
        settings_url = f"{base_url}/app/workspaces/{shared_id}/settings"
        owner.goto(settings_url, wait_until="networkidle")

        login_invite = create_invitation(owner, role="editor")
        existing_email = f"workspace-slice05-login-{uuid4()}@example.test"
        existing_context = browser.new_context()
        existing = existing_context.new_page()
        try_register(existing, base_url=base_url, email=existing_email, password=password)
        existing_context.clear_cookies()
        login_from_invitation(
            existing,
            email=existing_email,
            invite_url=login_invite,
            password=password,
        )
        expect(existing.get_by_text(shared_name)).to_be_visible()
        assert accept(existing, expected_role="editor", invite_url=login_invite) == shared_id
        existing.goto(login_invite, wait_until="networkidle")
        expect(existing.get_by_text(UNAVAILABLE)).to_be_visible()

        owner.goto(settings_url, wait_until="networkidle")
        signup_invite = create_invitation(owner, role="viewer")
        signup_context = browser.new_context(viewport={"width": 390, "height": 844})
        signup = signup_context.new_page()
        signup_email = f"workspace-slice05-signup-{uuid4()}@example.test"
        register_from_invitation(
            signup,
            email=signup_email,
            invite_url=signup_invite,
            password=password,
        )
        expect(signup.get_by_text(shared_name)).to_be_visible()
        signup.screenshot(path=output_dir / "invitation-authenticated-mobile.png", full_page=True)
        metrics = page_metrics(signup)
        assert metrics["overflowPx"] == 0, metrics
        assert metrics["undersizedTargets"] == [], metrics
        assert accept(signup, expected_role="viewer", invite_url=signup_invite) == shared_id

        owner.goto(settings_url, wait_until="networkidle")
        revoked_invite = create_invitation(owner, role="analyst")
        invitation_list = api_json(owner, f"/api/v1/workspaces/{shared_id}/invitations")["body"]
        revoked = invitation_list["items"][0]
        session = api_json(owner, "/api/v1/session")["body"]
        revoked_result = api_json(
            owner,
            f"/api/v1/workspaces/{shared_id}/invitations/{revoked['id']}/revoke",
            {
                "body": json.dumps({"expectedUpdatedAt": revoked["updatedAt"]}),
                "headers": {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session["csrfToken"],
                },
                "method": "POST",
            },
        )
        assert revoked_result["status"] == 200

        public_context = browser.new_context(viewport={"width": 1440, "height": 900})
        public = public_context.new_page()
        invalid_url = f"{base_url}/workspaces/invitations/not-a-real-credential"
        outcomes = []
        for label, url in (("revoked", revoked_invite), ("invalid", invalid_url)):
            response = public.goto(url, wait_until="networkidle")
            assert response is not None
            assert response.headers.get("cache-control") == "no-store"
            assert response.headers.get("referrer-policy") == "no-referrer"
            expect(public.get_by_text(UNAVAILABLE)).to_be_visible()
            outcomes.append(
                {"label": label, "message": public.get_by_text(UNAVAILABLE).inner_text()}
            )
        public.goto(revoked_invite, wait_until="networkidle")
        public.screenshot(path=output_dir / "invitation-unavailable-desktop.png", full_page=True)

        (output_dir / "report.json").write_text(
            json.dumps(
                {
                    "sharedWorkspaceId": shared_id,
                    "existingUserLoginReturn": True,
                    "newUserSignupReturn": True,
                    "atomicSessionSwitch": True,
                    "replayIsUnavailable": True,
                    "safeOutcomes": outcomes,
                    "screenshots": [
                        "invitation-authenticated-mobile.png",
                        "invitation-unavailable-desktop.png",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        public_context.close()
        signup_context.close()
        existing_context.close()
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
        default=Path("/tmp/booker-workspaces-slice05-browser"),
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
    print(f"Workspaces Slice 5 browser gate passed: {args.output_dir}")


if __name__ == "__main__":
    main()
