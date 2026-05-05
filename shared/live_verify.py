"""live_verify.py — reusable live-URL post-deploy verifier for any
xcerebro-builds county.

This module exists because local Playwright tests the build, not what the
user actually sees. Curl returns HTTP 200 on the HTML shell even when the
JS that fetches data fails. Verification gates must test the user-visible
outcome, not the code intent.

Public API:

    diagnose_live(live_url, json_path="data/leads.json", repo_path=None)
        -> dict
        Read-only diagnosis of a deployed dashboard. Categorizes the state
        into one of A-G (see DIAGNOSIS_CATEGORIES). Pure read-only.

    verify_live(live_url, min_rows=5, timeout_seconds=60,
                screenshot_path=None, proof_path=None)
        -> dict
        Loads the live URL with `?view=all` forced in headless Chrome,
        waits for `tbody tr.row-anchor` rows, captures screenshot + first
        N PIDs/addresses + console errors. Returns a proof dict. Sets
        `ok=False` on any sub-check failure or timeout.

    run_full_live_verification(live_url, repo_path)
        -> int
        End-to-end gate. Returns:
            0 = verified (live URL renders >=5 rows)
            1 = recoverable failure (category A-F) — caller should fix
            2 = unknown / category G — manual investigation needed

Usage from a county verify.py:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    import live_verify

    rc = live_verify.run_full_live_verification(
        "https://xcerebroai.github.io/<county>-intel/",
        repo_path=str(Path(__file__).resolve().parents[1]),
    )
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ============================================================================
# Diagnosis taxonomy — the contract. Do not invent categories without
# updating the spec.
# ============================================================================
DIAGNOSIS_CATEGORIES = {
    "A": "JSON FILE NOT DEPLOYED",
    "B": "STALE DEPLOY",
    "C": "JS ERROR",
    "D": "CORS / FETCH PATH",
    "E": "SLOW JSON FETCH",
    "F": "CACHE LAG",
    "G": "UNKNOWN",
    "OK": "live URL renders rows correctly (no failure)",
}

# How long to wait for browser-side render (loaded HTML shell + JS exec
# + JSON fetch + table population)
DEFAULT_RENDER_TIMEOUT_MS = 60_000


# ============================================================================
# Low-level helpers
# ============================================================================

def _http_head(url: str, timeout: int = 15) -> dict:
    """Returns dict with status, content_length, last_modified, etag,
    error if any."""
    out = {"url": url, "status": None, "content_length": None,
           "last_modified": None, "etag": None, "error": None}
    try:
        req = urllib.request.Request(
            url, method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (xcerebro-builds live_verify)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out["status"] = resp.status
            out["content_length"] = int(resp.headers.get("Content-Length") or 0) or None
            out["last_modified"] = resp.headers.get("Last-Modified")
            out["etag"] = resp.headers.get("ETag")
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["error"] = str(e)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _git_short_sha(repo_path: Optional[str]) -> Optional[str]:
    if not repo_path:
        return None
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path,
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _gh_pages_status(owner_repo: str) -> dict:
    """Return latest Pages build status via gh CLI. owner_repo = 'owner/repo'."""
    out = {"status": None, "commit": None, "error": None,
           "duration_ms": None, "created_at": None}
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}/pages/builds/latest"],
            capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            out["error"] = r.stderr.strip() or "gh api failed"
            return out
        d = json.loads(r.stdout)
        out["status"] = d.get("status")
        out["commit"] = d.get("commit")
        out["created_at"] = d.get("created_at")
        out["duration_ms"] = d.get("duration")
        err = d.get("error")
        if isinstance(err, dict):
            out["error"] = err.get("message")
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _derive_owner_repo_from_url(live_url: str) -> Optional[str]:
    """https://owner.github.io/repo/ -> 'owner/repo'."""
    m = re.match(r"^https?://([^.]+)\.github\.io/([^/?#]+)", live_url)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def _derive_owner_repo_from_git(repo_path: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=repo_path,
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
        url = r.stdout.strip()
        # https://github.com/owner/repo.git or git@github.com:owner/repo.git
        m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        pass
    return None


# ============================================================================
# diagnose_live
# ============================================================================

def diagnose_live(
    live_url: str,
    json_path: str = "data/leads.json",
    repo_path: Optional[str] = None,
) -> dict:
    """Read-only diagnosis. Returns:
        {
          "category": "A".."G" or "OK",
          "category_label": str,
          "evidence": { ... },
          "actionable": bool,  # True for A-F, False for G/OK
        }
    """
    base = live_url.rstrip("/")
    json_url = f"{base}/{json_path.lstrip('/')}"

    evidence = {
        "live_url": live_url,
        "json_url": json_url,
        "html_head": _http_head(base + "/"),
        "json_head": _http_head(json_url),
        "pages_build": None,
        "local_head": _git_short_sha(repo_path),
        "browser": None,
    }

    # Pages build status
    owner_repo = (
        _derive_owner_repo_from_url(live_url)
        or (_derive_owner_repo_from_git(repo_path) if repo_path else None)
    )
    if owner_repo:
        evidence["pages_build"] = _gh_pages_status(owner_repo)
        evidence["owner_repo"] = owner_repo

    # ---- Category A: JSON not deployed ----
    json_status = evidence["json_head"]["status"]
    if json_status is None or json_status >= 400:
        return {
            "category": "A",
            "category_label": DIAGNOSIS_CATEGORIES["A"],
            "evidence": evidence,
            "actionable": True,
            "summary": f"data/leads.json returns HTTP {json_status} on the live URL.",
        }

    # ---- Category B: Stale deploy ----
    pb = evidence["pages_build"] or {}
    if pb.get("commit") and evidence["local_head"]:
        if pb["commit"] != evidence["local_head"]:
            # If local is ahead of pages by more than 1 commit, classify B
            return {
                "category": "B",
                "category_label": DIAGNOSIS_CATEGORIES["B"],
                "evidence": evidence,
                "actionable": True,
                "summary": (f"Pages deployed commit {pb['commit'][:8]} != "
                            f"local HEAD {evidence['local_head'][:8]}."),
            }
    if pb.get("status") and pb["status"] not in ("built", None):
        return {
            "category": "B",
            "category_label": DIAGNOSIS_CATEGORIES["B"],
            "evidence": evidence,
            "actionable": True,
            "summary": f"Pages build status = {pb['status']} (not 'built').",
        }

    # ---- Browser-driven checks (C, D, E, G) ----
    browser_result = _playwright_load(
        f"{base}/?view=all", min_rows=5, timeout_ms=DEFAULT_RENDER_TIMEOUT_MS
    )
    evidence["browser"] = browser_result

    if browser_result.get("error") and "Playwright not available" in browser_result["error"]:
        return {
            "category": "G",
            "category_label": DIAGNOSIS_CATEGORIES["G"],
            "evidence": evidence,
            "actionable": False,
            "summary": "Playwright unavailable; cannot diagnose JS execution.",
        }

    # ---- Category C: JS error ----
    if browser_result.get("page_errors") or browser_result.get("console_errors"):
        return {
            "category": "C",
            "category_label": DIAGNOSIS_CATEGORIES["C"],
            "evidence": evidence,
            "actionable": True,
            "summary": (f"Browser console reported errors: "
                        f"{browser_result.get('console_errors', [])[:3]}"),
        }

    # ---- Category D: CORS / fetch path ----
    failed = [r for r in browser_result.get("failed_requests", [])
              if "leads.json" in (r.get("url") or "")]
    if failed:
        return {
            "category": "D",
            "category_label": DIAGNOSIS_CATEGORIES["D"],
            "evidence": evidence,
            "actionable": True,
            "summary": f"leads.json fetch failed in browser: {failed[0]}",
        }

    # ---- Category E: Slow JSON fetch ----
    fetch_ms = browser_result.get("leads_json_fetch_ms")
    if fetch_ms is not None and fetch_ms > 30_000:
        return {
            "category": "E",
            "category_label": DIAGNOSIS_CATEGORIES["E"],
            "evidence": evidence,
            "actionable": True,
            "summary": f"leads.json fetch took {fetch_ms}ms (>30s).",
        }

    # ---- Category F: Cache lag ----
    # If Pages build is current but Last-Modified is older than 12 hours
    # behind the build's created_at, treat as cache lag.
    if pb.get("created_at") and evidence["html_head"].get("last_modified"):
        try:
            built_at = datetime.fromisoformat(pb["created_at"].replace("Z", "+00:00"))
            lm = evidence["html_head"]["last_modified"]
            # Last-Modified is RFC 1123: "Tue, 05 May 2026 15:08:51 GMT"
            from email.utils import parsedate_to_datetime
            served_at = parsedate_to_datetime(lm)
            if (built_at - served_at).total_seconds() > 12 * 3600:
                return {
                    "category": "F",
                    "category_label": DIAGNOSIS_CATEGORIES["F"],
                    "evidence": evidence,
                    "actionable": True,
                    "summary": (f"CDN serving stale content: build={built_at} "
                                f"served={served_at}"),
                }
        except Exception:
            pass

    # ---- OK or G ----
    if browser_result.get("ok"):
        return {
            "category": "OK",
            "category_label": DIAGNOSIS_CATEGORIES["OK"],
            "evidence": evidence,
            "actionable": False,
            "summary": (f"Live URL renders {browser_result['row_count']} rows. "
                        f"No failure detected."),
        }

    return {
        "category": "G",
        "category_label": DIAGNOSIS_CATEGORIES["G"],
        "evidence": evidence,
        "actionable": False,
        "summary": (f"Browser loaded the live URL without errors but did not "
                    f"render >=5 rows ({browser_result.get('row_count', 0)} found). "
                    f"Manual investigation required."),
    }


# ============================================================================
# Browser driver — internal
# ============================================================================

def _playwright_load(url: str, min_rows: int = 5,
                     timeout_ms: int = DEFAULT_RENDER_TIMEOUT_MS,
                     screenshot_path: Optional[str] = None,
                     ) -> dict:
    """Single Playwright run. Returns:
        {
          "ok": bool,
          "url": str,
          "row_count": int,
          "first_5_pids": [...],
          "first_5_addresses": [...],
          "console_errors": [...],
          "page_errors": [...],
          "failed_requests": [...],
          "html_title": str,
          "leads_json_fetch_ms": int|None,
          "elapsed_ms": int,
          "error": str|None,
        }
    """
    out = {
        "ok": False, "url": url, "row_count": 0,
        "first_5_pids": [], "first_5_addresses": [],
        "console_errors": [], "page_errors": [], "failed_requests": [],
        "html_title": "", "leads_json_fetch_ms": None,
        "elapsed_ms": None, "error": None,
    }
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        out["error"] = f"Playwright not available: {e}"
        return out

    t0 = time.time()
    json_t0 = None
    json_t1 = None
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            out["error"] = f"chromium.launch failed: {e}"
            return out
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        page.on("pageerror", lambda exc: out["page_errors"].append(str(exc)))
        page.on("console", lambda m: out["console_errors"].append(m.text)
                if m.type == "error" else None)

        def on_request(req):
            nonlocal json_t0
            if "leads.json" in req.url and json_t0 is None:
                json_t0 = time.time()

        def on_response(resp):
            nonlocal json_t1
            if "leads.json" in resp.url and json_t1 is None:
                json_t1 = time.time()
            if resp.status >= 400:
                out["failed_requests"].append({
                    "url": resp.url, "status": resp.status, "error": None,
                })

        def on_requestfailed(req):
            out["failed_requests"].append({
                "url": req.url, "status": None,
                "error": req.failure or "request failed",
            })

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_requestfailed)

        try:
            page.goto(url, wait_until="load", timeout=timeout_ms)
        except Exception as e:
            out["error"] = f"goto failed: {e}"
            browser.close()
            return out

        out["html_title"] = page.title()

        try:
            page.wait_for_function(
                f"() => document.querySelectorAll('tbody tr.row-anchor').length >= {min_rows}",
                timeout=timeout_ms,
            )
        except Exception:
            pass

        rows = page.locator("tbody tr.row-anchor")
        row_count = rows.count()
        out["row_count"] = row_count

        for i in range(min(5, row_count)):
            try:
                pid = rows.nth(i).locator(".pid-link").first.inner_text().strip()
                addr = rows.nth(i).locator(".addr").first.inner_text().strip()
                out["first_5_pids"].append(pid)
                out["first_5_addresses"].append(addr)
            except Exception:
                pass

        if screenshot_path:
            try:
                Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=False)
            except Exception as e:
                out["error"] = (out["error"] or "") + f" screenshot: {e}"

        browser.close()

    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    if json_t0 and json_t1:
        out["leads_json_fetch_ms"] = int((json_t1 - json_t0) * 1000)

    out["ok"] = (
        out["row_count"] >= min_rows
        and not out["page_errors"]
        and not [e for e in out["console_errors"] if "favicon" not in e.lower()]
        and out["error"] is None
    )
    return out


# ============================================================================
# verify_live (Phase 3)
# ============================================================================

def verify_live(
    live_url: str,
    min_rows: int = 5,
    timeout_seconds: int = 60,
    screenshot_path: Optional[str] = None,
    proof_path: Optional[str] = None,
) -> dict:
    """Phase 3 verifier. Forces ?view=all on the live URL, waits for >=5
    real lead rows, captures proof. Returns a dict with `ok`, `url`,
    `verified_at`, `row_count`, `first_5_pids`, `first_5_addresses`,
    `screenshot_path`, `console_errors`, `failed_requests`.

    Side effects:
      - writes screenshot to `screenshot_path` if provided
      - writes JSON proof to `proof_path` if provided
    """
    base = live_url.rstrip("/")
    if "?" in base:
        all_url = base + "&view=all"
    else:
        all_url = base + "/?view=all"

    timeout_ms = max(timeout_seconds * 1000, 5000)
    browser_result = _playwright_load(
        all_url, min_rows=min_rows, timeout_ms=timeout_ms,
        screenshot_path=screenshot_path,
    )

    proof = {
        "ok": browser_result["ok"],
        "url": all_url,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "row_count": browser_result["row_count"],
        "first_5_pids": browser_result["first_5_pids"],
        "first_5_addresses": browser_result["first_5_addresses"],
        "screenshot_path": screenshot_path,
        "console_errors": browser_result["console_errors"],
        "page_errors": browser_result["page_errors"],
        "failed_requests": browser_result["failed_requests"],
        "leads_json_fetch_ms": browser_result["leads_json_fetch_ms"],
        "elapsed_ms": browser_result["elapsed_ms"],
        "error": browser_result["error"],
    }

    if not proof["ok"] and not proof["error"]:
        proof["error"] = (
            f"min_rows={min_rows} not reached "
            f"(rendered={proof['row_count']}); "
            f"page_errors={len(proof['page_errors'])} "
            f"console_errors={len(proof['console_errors'])}"
        )

    if proof_path:
        Path(proof_path).parent.mkdir(parents=True, exist_ok=True)
        Path(proof_path).write_text(
            json.dumps(proof, indent=2, default=str), encoding="utf-8"
        )

    return proof


# ============================================================================
# run_full_live_verification (the gate)
# ============================================================================

def run_full_live_verification(
    live_url: str,
    repo_path: str,
    min_rows: int = 5,
    timeout_seconds: int = 60,
) -> int:
    """End-to-end gate.

    Returns:
      0 = verified (live URL renders >=min_rows rows, no errors)
      1 = recoverable failure (category A-F) — caller should fix and retry
      2 = unknown / category G — manual investigation needed

    Writes proof to {repo_path}/data/raw/live_verification.json and
    screenshot to {repo_path}/docs/live_dashboard.png.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    repo = Path(repo_path)
    proof_path = repo / "data" / "raw" / "live_verification.json"
    screenshot_path = repo / "docs" / "live_dashboard.png"

    print(f"[live_verify] live_url     = {live_url}")
    print(f"[live_verify] repo_path    = {repo_path}")
    print(f"[live_verify] proof_path   = {proof_path}")
    print(f"[live_verify] screenshot   = {screenshot_path}")
    print(f"[live_verify] min_rows     = {min_rows}")
    print()

    # Try the verification first — if it succeeds, no need to diagnose.
    proof = verify_live(
        live_url, min_rows=min_rows, timeout_seconds=timeout_seconds,
        screenshot_path=str(screenshot_path),
        proof_path=str(proof_path),
    )

    if proof["ok"]:
        print(f"  ✓ PASS — {proof['row_count']} rows rendered at "
              f"{proof['url']}")
        if proof["first_5_addresses"]:
            print(f"  first 5 addresses:")
            for pid, addr in zip(proof["first_5_pids"], proof["first_5_addresses"]):
                print(f"    - {pid}  {addr}")
        return 0

    print(f"  ✗ verification did not render >={min_rows} rows; running diagnosis")
    print(f"    error: {proof['error']}")
    print(f"    row_count: {proof['row_count']}")
    print()

    diag = diagnose_live(live_url, repo_path=repo_path)
    cat = diag["category"]
    print(f"  diagnosis category: {cat} — {diag['category_label']}")
    print(f"  summary: {diag['summary']}")

    if cat in ("A", "B", "C", "D", "E", "F"):
        print(f"  → recoverable; caller should apply matching fix")
        return 1
    if cat == "OK":
        # Edge case — diagnose says ok, but verify_live failed. Treat as G.
        print(f"  → diagnosis says OK but verify failed; treating as UNKNOWN")
        return 2
    return 2


# ============================================================================
# CLI entrypoint
# ============================================================================

def _main(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Live URL post-deploy verifier.")
    ap.add_argument("--url", required=True,
                    help="Live URL (e.g. https://owner.github.io/repo/)")
    ap.add_argument("--repo", default=".",
                    help="Local repo path (default cwd)")
    ap.add_argument("--min-rows", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--mode", choices=["verify", "diagnose", "full"],
                    default="full")
    args = ap.parse_args(argv)

    if args.mode == "diagnose":
        d = diagnose_live(args.url, repo_path=args.repo)
        print(json.dumps(d, indent=2, default=str))
        return 0

    if args.mode == "verify":
        repo = Path(args.repo)
        screenshot_path = repo / "docs" / "live_dashboard.png"
        proof_path = repo / "data" / "raw" / "live_verification.json"
        p = verify_live(args.url, min_rows=args.min_rows,
                        timeout_seconds=args.timeout,
                        screenshot_path=str(screenshot_path),
                        proof_path=str(proof_path))
        print(json.dumps({k: v for k, v in p.items() if k != "evidence"},
                         indent=2, default=str))
        return 0 if p["ok"] else 1

    return run_full_live_verification(
        args.url, args.repo,
        min_rows=args.min_rows, timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
