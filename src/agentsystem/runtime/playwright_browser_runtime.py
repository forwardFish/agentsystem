from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from agentsystem.runtime.browser_session_manager import BrowserSessionManager


DEFAULT_VIEWPORTS: tuple[tuple[str, dict[str, int]], ...] = (
    ("desktop", {"width": 1440, "height": 900}),
    ("mobile", {"width": 390, "height": 844}),
)


@dataclass(slots=True)
class BrowserTarget:
    url: str
    name: str
    kind: str = "current"
    actions: list[dict[str, Any]] = field(default_factory=list)
    viewports: list[dict[str, Any]] = field(default_factory=list)


def run_browser_capture(
    manager: BrowserSessionManager,
    targets: list[BrowserTarget],
    *,
    headless: bool = True,
) -> dict[str, Any]:
    snapshot = manager.ensure_session(target_url=targets[0].url if targets else None)
    results: list[dict[str, Any]] = []

    if not targets:
        return {"snapshot": snapshot, "results": results}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            ignore_https_errors=True,
            storage_state=str(manager.storage_state_file) if manager.storage_state_file.exists() else None,
        )
        try:
            for target in targets:
                for viewport_name, viewport in _resolve_viewports(target.viewports):
                    results.append(
                        _capture_target(
                            manager,
                            context,
                            target=target,
                            viewport_name=viewport_name,
                            viewport=viewport,
                        )
                    )
            context.storage_state(path=str(manager.storage_state_file))
        finally:
            context.close()
            browser.close()

    return {"snapshot": snapshot, "results": results}


def _capture_target(
    manager: BrowserSessionManager,
    context,
    *,
    target: BrowserTarget,
    viewport_name: str,
    viewport: dict[str, int],
) -> dict[str, Any]:
    page = context.new_page()
    page.set_viewport_size(viewport)

    console_messages: list[dict[str, str]] = []
    request_failures: list[str] = []
    page_errors: list[str] = []

    page.on(
        "console",
        lambda message: console_messages.append(
            {
                "type": message.type,
                "text": message.text,
                "location": str(message.location or {}),
            }
        ),
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "requestfailed",
        lambda request: request_failures.append(
            f"{request.method} {request.url} -> {_request_failure_text(request)}"
        ),
    )

    status_code = 0
    blocking_findings: list[str] = []
    important_findings: list[str] = []
    screenshot_path = ""
    dom_path = ""
    console_path = ""
    observation_path = ""
    observation_payload: dict[str, Any] = {}
    title = ""
    excerpt = ""
    final_url = target.url

    try:
        manager.record_step(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "target": target.name,
                "kind": target.kind,
                "viewport": viewport_name,
                "action": "goto",
                "url": target.url,
            }
        )
        response = page.goto(target.url, wait_until="domcontentloaded", timeout=30000)
        status_code = response.status if response is not None else 0
        final_url = page.url
        _wait_for_settle(page)
        _run_actions(page, manager, target, viewport_name)
        title = page.title()
        html = page.content()
        excerpt = _extract_excerpt(page)
        screenshot_path = str(manager.allocate_screenshot_path(f"{target.name}-{viewport_name}"))
        page.screenshot(path=screenshot_path, full_page=True)
        dom_path = manager.write_dom_snapshot(f"{target.name}-{viewport_name}", html)

        observation = _build_observation(page, target, viewport_name, viewport)
        observation.update(
            {
                "title": title,
                "status_code": status_code,
                "final_url": final_url,
                "screenshot_path": screenshot_path,
                "dom_path": dom_path,
                "excerpt": excerpt,
                "request_failures": request_failures,
                "page_errors": page_errors,
            }
        )
        observation_payload = dict(observation)

        console_path = manager.write_console_log(f"{target.name}-{viewport_name}", console_messages)
        observation["console_log_path"] = console_path
        observation_path = manager.record_observation(f"{target.name}-{viewport_name}", observation)
        observation_payload["console_log_path"] = console_path
        observation_payload["observation_path"] = observation_path

        blocking_findings.extend(_find_blocking_issues(status_code, final_url, page_errors, request_failures))
        important_findings.extend(_find_important_issues(title, observation, console_messages))
    except PlaywrightError as exc:
        blocking_findings.append(f"{target.url} failed in {viewport_name} viewport: {exc}")
    finally:
        page.close()

    return {
        "name": target.name,
        "url": target.url,
        "kind": target.kind,
        "viewport": viewport,
        "viewport_name": viewport_name,
        **observation_payload,
        "status_code": status_code,
        "title": title,
        "excerpt": excerpt,
        "final_url": final_url,
        "screenshot_path": screenshot_path,
        "dom_path": dom_path,
        "console_log_path": console_path,
        "observation_path": observation_path,
        "console_messages": console_messages,
        "request_failures": request_failures,
        "page_errors": page_errors,
        "blocking_findings": blocking_findings,
        "important_findings": important_findings,
    }


def _wait_for_settle(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightError:
        try:
            page.wait_for_timeout(1200)
        except PlaywrightError:
            return


def _run_actions(page: Page, manager: BrowserSessionManager, target: BrowserTarget, viewport_name: str) -> None:
    for index, action in enumerate(target.actions, start=1):
        kind = str(action.get("type") or action.get("action") or "").strip().lower()
        if not kind:
            continue
        manager.record_step(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "target": target.name,
                "viewport": viewport_name,
                "action": kind,
                "payload": action,
            }
        )
        try:
            if kind == "click":
                page.locator(str(action.get("selector") or "")).first.click(timeout=10000)
                _wait_for_settle(page)
            elif kind == "type":
                selector = str(action.get("selector") or "").strip()
                page.locator(selector).first.fill(str(action.get("value") or ""))
            elif kind == "wait":
                page.wait_for_timeout(int(action.get("ms") or 1000))
            elif kind == "goto":
                page.goto(str(action.get("url") or target.url), wait_until="domcontentloaded", timeout=30000)
                _wait_for_settle(page)
            elif kind == "capture":
                screenshot_path = str(manager.allocate_screenshot_path(f"{target.name}-{viewport_name}-step-{index}"))
                page.screenshot(path=screenshot_path, full_page=True)
        except PlaywrightError:
            continue


def _resolve_viewports(raw_viewports: list[dict[str, Any]]) -> list[tuple[str, dict[str, int]]]:
    if not raw_viewports:
        return list(DEFAULT_VIEWPORTS)
    result: list[tuple[str, dict[str, int]]] = []
    for item in raw_viewports:
        label = str(item.get("name") or item.get("label") or "custom").strip() or "custom"
        width = int(item.get("width") or 1440)
        height = int(item.get("height") or 900)
        result.append((label, {"width": width, "height": height}))
    return result or list(DEFAULT_VIEWPORTS)


def _build_observation(page: Page, target: BrowserTarget, viewport_name: str, viewport: dict[str, int]) -> dict[str, Any]:
    payload = page.evaluate(
        """() => {
            const textList = (selectors, limit = 12) =>
              Array.from(document.querySelectorAll(selectors))
                .map((node) => (node.textContent || "").replace(/\\s+/g, " ").trim())
                .filter(Boolean)
                .slice(0, limit);
            const bodyText = (document.body?.innerText || "").replace(/\\s+/g, " ").trim();
            const hasSearch = !!document.querySelector('input[type="search"], input[placeholder*="search" i], form input[name*="search" i]');
            const statBlocks = textList('[class*="stat" i], [class*="metric" i], [data-stat]', 10);
            const filterLabels = textList('aside label, form label, [aria-label*="filter" i], [class*="filter" i] label', 12);
            const sponsorLabels = textList('[class*="sponsor" i], [data-sponsored], [class*="featured" i]', 10);
            const viewControls = textList('[data-view-controls] a, [data-view-controls] button, [role="tab"], [class*="tab" i] a, [class*="tab" i] button', 16);
            const matrixHeaders = textList('[data-matrix-section] th, table th, [class*="matrix" i] th', 16);
            const riskLabels = textList('[data-risk-section] h2, [data-risk-section] h3, [data-risk-section] li, [class*="risk" i] h2, [class*="risk" i] h3', 16);
            const evidenceLabels = textList('[data-evidence-block] strong, [data-evidence-block] h3, [class*="evidence" i] strong, [class*="evidence" i] h3', 16);
            const refreshStateEl = document.querySelector('[data-refresh-state]');
            const refreshMessage = ((refreshStateEl?.querySelector('.refresh-text')?.textContent || '')).replace(/\\s+/g, ' ').trim();
            const refreshPresent = !!refreshStateEl || Array.from(document.querySelectorAll('button')).some((node) => /刷新|抓取|refresh/i.test(node.textContent || ''));
            const cards = document.querySelectorAll('article, [class*="card" i], [data-card]').length;
            return {
              nav_items: textList('nav a, header a, [role="navigation"] a', 16),
              headings: textList('h1, h2, h3', 16),
              cta_labels: textList('main a, main button', 16),
              tabs: textList('[role="tab"], [aria-selected="true"], main button, main a', 16),
              category_labels: textList('[class*="category" i] a, [class*="category" i] button, [data-category]', 16),
              content_sections: textList('main section h2, main section h3', 16),
              filter_labels: filterLabels,
              sponsor_labels: sponsorLabels,
              stat_blocks: statBlocks,
              view_controls: viewControls,
              matrix_headers: matrixHeaders,
              risk_labels: riskLabels,
              evidence_labels: evidenceLabels,
              refresh_state: refreshStateEl?.getAttribute('data-refresh-state') || '',
              refresh_message: refreshMessage,
              search_present: hasSearch,
              matrix_present: matrixHeaders.length > 0,
              risk_present: riskLabels.length > 0,
              evidence_present: evidenceLabels.length > 0,
              refresh_present: refreshPresent,
              nav_count: textList('nav a, header a, [role="navigation"] a', 32).length,
              heading_count: textList('h1, h2, h3', 32).length,
              cta_count: textList('main a, main button', 32).length,
              tab_count: textList('[role="tab"], [aria-selected="true"], main button, main a', 32).length,
              category_count: textList('[class*="category" i] a, [class*="category" i] button, [data-category]', 32).length,
              filter_count: filterLabels.length,
              sponsor_count: sponsorLabels.length,
              stat_count: statBlocks.length,
              view_count: viewControls.length,
              matrix_count: matrixHeaders.length,
              risk_count: riskLabels.length,
              evidence_count: evidenceLabels.length,
              card_count: cards,
              excerpt: bodyText.slice(0, 1200),
            };
        }"""
    )
    return {
        "target_name": target.name,
        "kind": target.kind,
        "url": target.url,
        "viewport_name": viewport_name,
        "viewport": viewport,
        **payload,
    }


def _find_blocking_issues(
    status_code: int,
    final_url: str,
    page_errors: list[str],
    request_failures: list[str],
) -> list[str]:
    findings: list[str] = []
    if status_code >= 400:
        findings.append(f"{final_url} returned HTTP {status_code}.")
    for error in page_errors[:5]:
        findings.append(f"Page runtime error: {error}")
    for failure in request_failures[:5]:
        if _is_ignorable_request_failure(failure):
            continue
        findings.append(f"Critical request failed: {failure}")
    return findings


def _find_important_issues(
    title: str,
    observation: dict[str, Any],
    console_messages: list[dict[str, str]],
) -> list[str]:
    findings: list[str] = []
    if not title:
        findings.append("Page is missing a clear title.")
    error_logs = [item["text"] for item in console_messages if item.get("type") == "error"]
    for log in error_logs[:3]:
        findings.append(f"Console error: {log}")
    if not observation.get("headings"):
        findings.append("No visible heading hierarchy was detected.")
    return findings


def _extract_excerpt(page: Page) -> str:
    try:
        text = page.locator("body").inner_text(timeout=5000)
    except PlaywrightError:
        return ""
    return " ".join(text.split())[:600]


def _request_failure_text(request) -> str:
    failure = request.failure
    if failure is None:
        return "request failed"
    if isinstance(failure, str):
        return failure
    error_text = getattr(failure, "error_text", None)
    if isinstance(error_text, str) and error_text.strip():
        return error_text
    if isinstance(failure, dict):
        text = str(failure.get("errorText") or failure.get("error_text") or "").strip()
        if text:
            return text
    return str(failure)


def _is_ignorable_request_failure(failure: str) -> bool:
    text = str(failure or "").strip()
    if not text:
        return True
    if "_rsc=" in text and "ERR_ABORTED" in text:
        return True
    if "ERR_BLOCKED_BY_ORB" in text:
        return True
    return False
