#!/usr/bin/env python3
"""Build the live index.html from the Fabrik Site Studio.

Usage:
  python3 tools/export_site.py --studio studio.html --draft draft.json [--out index.html]

  --studio  The Studio page (the artifact's index.html, read with the Artifact tool).
  --draft   The Studio's site/draft document as JSON ({"state": ..., "updatedAt": ...}).
  --out     Where to write the site (default: index.html next to this folder).

What it does:
  1. Opens the Studio headless with no network and no claude.ai runtime, so it boots from
     the draft placed in its browser storage.
  2. Asks the Studio for exactly what "Download HTML" would save (window.FabrikStudioBuild).
  3. Makes it live-ready: Adobe Fonts kit -> cib4apc (the Studio carries a preview kit),
     no noindex. CNAME and robots.txt are left alone.
  4. Refuses to write anything that does not look like a complete site.

Exit codes: 0 written, 3 unchanged (nothing to commit), 1 failed.
"""
import argparse
import asyncio
import json
import pathlib
import re
import sys

LIVE_KIT = "https://use.typekit.net/cib4apc.css"


async def build(studio: pathlib.Path, draft: dict) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # No network: fonts and CDNs are irrelevant to building the document.
        await page.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
        await page.add_init_script(
            "try{localStorage.setItem('fabrikStudioDraft'," + json.dumps(json.dumps(draft)) + ")}catch(e){}"
        )
        await page.goto(studio.resolve().as_uri())
        await page.wait_for_function(
            "typeof window.FabrikStudioBuild === 'function' && "
            "/Not syncing/.test((document.getElementById('status') || {}).textContent || '')",
            timeout=60000,
        )
        html = await page.evaluate("window.FabrikStudioBuild()")
        await browser.close()
    if errors:
        print("Studio page errors while building:", *errors[:5], sep="\n  ", file=sys.stderr)
    return html


def make_live(html: str) -> str:
    html = re.sub(r"https://use\.typekit\.net/[a-z0-9]+\.css", LIVE_KIT, html)
    html = re.sub(r'<meta name="robots"[^>]*>', "", html)
    return html


def check(html: str) -> list:
    problems = []
    if len(html) < 100_000:
        problems.append(f"too small ({len(html)} bytes)")
    for must in ('id="site-state"', 'className+=" fk-wait"', LIVE_KIT, "</html>"):
        if must not in html:
            problems.append(f"missing {must}")
    # editor-only markers (the runtime itself mentions both names, so match the exact preview lines)
    for never in ("<script>window.FABRIK_EDITOR=1", 'className+=" fk-edit"', 'name="robots"'):
        if never in html:
            problems.append(f"contains {never}")
    return problems


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--studio", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", default=str(here / "index.html"))
    a = ap.parse_args()

    draft = json.loads(pathlib.Path(a.draft).read_text(encoding="utf8"))
    if "state" not in draft:
        draft = {"state": draft, "updatedAt": 0}

    html = make_live(asyncio.run(build(pathlib.Path(a.studio), draft)))
    problems = check(html)
    if problems:
        print("Not written, the export looks wrong: " + "; ".join(problems), file=sys.stderr)
        return 1

    out = pathlib.Path(a.out)
    if out.exists() and out.read_text(encoding="utf8") == html:
        print("Unchanged: the live site already matches this draft.")
        return 3
    out.write_text(html, encoding="utf8")
    print(f"Wrote {out} ({len(html):,} bytes) from draft saved {draft.get('updatedAt')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
