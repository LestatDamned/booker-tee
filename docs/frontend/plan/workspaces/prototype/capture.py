"""Capture the standalone Workspaces Slice 1 visual prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000},
    "tablet": {"width": 920, "height": 900},
    "mobile": {"width": 390, "height": 844},
}
MOCHA_STATES = ("default", "create", "loading", "empty", "pending", "conflict")
LATTE_STATES = ("default", "create")


def capture(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prototype_uri = Path(__file__).with_name("index.html").resolve().as_uri()
    results: list[dict[str, object]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for theme, states in (("mocha", MOCHA_STATES), ("latte", LATTE_STATES)):
            for state in states:
                for viewport_name, viewport in VIEWPORTS.items():
                    page = browser.new_page(viewport=viewport)
                    console_errors: list[str] = []
                    page_errors: list[str] = []
                    page.on(
                        "console",
                        lambda message, errors=console_errors: (
                            errors.append(message.text) if message.type == "error" else None
                        ),
                    )
                    page.on(
                        "pageerror",
                        lambda error, errors=page_errors: errors.append(str(error)),
                    )
                    query = urlencode({"state": state, "theme": theme})
                    page.goto(f"{prototype_uri}?{query}", wait_until="load")
                    page.emulate_media(reduced_motion="reduce")

                    metrics = page.evaluate(
                        """
                        () => {
                          const root = document.documentElement;
                          const targets = [...document.querySelectorAll(
                            'a[href], button:not([disabled]), input, select'
                          )].filter((element) => {
                            const style = getComputedStyle(element);
                            const rect = element.getBoundingClientRect();
                            return style.display !== 'none' &&
                              style.visibility !== 'hidden' &&
                              rect.width > 0 && rect.height > 0 &&
                              rect.bottom > 0 && rect.top < innerHeight;
                          });
                          return {
                            clientWidth: root.clientWidth,
                            scrollWidth: root.scrollWidth,
                            overflowPx: Math.max(0, root.scrollWidth - root.clientWidth),
                            focusedId: document.activeElement?.id || null,
                            undersizedTargets: targets
                              .map((element) => {
                                const rect = element.getBoundingClientRect();
                                return {
                                  label: element.getAttribute('aria-label') ||
                                    element.textContent?.trim() || element.id,
                                  width: Math.round(rect.width),
                                  height: Math.round(rect.height),
                                };
                              })
                              .filter((target) => target.width < 44 || target.height < 44),
                          };
                        }
                        """
                    )
                    screenshot_name = f"{theme}-{state}-{viewport_name}.png"
                    page.screenshot(
                        path=output_dir / screenshot_name,
                        full_page=state != "create",
                    )
                    results.append(
                        {
                            "theme": theme,
                            "state": state,
                            "viewport": viewport_name,
                            "screenshot": screenshot_name,
                            "metrics": metrics,
                            "consoleErrors": console_errors,
                            "pageErrors": page_errors,
                        }
                    )
                    page.close()
        browser.close()

    report: dict[str, object] = {
        "prototype": str(Path(__file__).with_name("index.html")),
        "results": results,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/booker-workspaces-slice01-prototype"),
    )
    args = parser.parse_args()
    report = capture(args.output)
    results = report["results"]
    assert isinstance(results, list)
    failed = [
        result
        for result in results
        if result["metrics"]["overflowPx"]
        or result["metrics"]["undersizedTargets"]
        or result["consoleErrors"]
        or result["pageErrors"]
    ]
    print(f"Captured {len(results)} prototype states in {args.output}")
    print(f"Geometry/browser failures: {len(failed)}")
    if failed:
        print(json.dumps(failed, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
