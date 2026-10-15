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
  3b. Ships only what visitors see: hidden sections out of the markup, their text out of the embedded
     state, unused colour themes dropped (prune()).
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


KEEP_KEYS = {"id", "type", "hidden", "target", "side"}


def _blank(o):
    """Empty every string in a hidden section's content, keeping the structure (ids, list lengths) the page's data keys rely on."""
    if isinstance(o, dict):
        return {k: (v if k in KEEP_KEYS else _blank(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [_blank(x) for x in o]
    return "" if isinstance(o, str) else o


def prune(html: str) -> str:
    """Ship only what visitors see (2026-10-14 audit): hidden sections leave the markup and their text leaves the embedded
    state; colour themes no section wears leave the state (551 themes, ~118 KB, for 12 in use)."""
    m = re.search(r'(<script type="application/json" id="site-state">)(.*?)(</script>)', html, re.S)
    if not m:
        return html
    st = json.loads(m.group(2))
    c = st.get("content", {})
    for b in c.get("blocks", []):
        if b.get("hidden"):
            b.update(_blank(b))
    for k in ("band", "work", "now", "ways", "principles"):
        if isinstance(c.get(k), dict) and c[k].get("hidden"):
            c[k] = _blank(c[k])
    used = set((st.get("sectionScheme") or {}).values())
    if st.get("schemes"):
        st["schemes"] = [x for x in st["schemes"] if x.get("id") in used]
    st.pop("schemeGen", None)
    js = json.dumps(st, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = html[: m.start(2)] + js + html[m.end(2):]
    # hidden sections and their menu links leave the markup. Only the page markup (<body> to </main>) is touched: the renderer's
    # own scripts contain the same section strings.
    a, z = html.find("<body>"), html.find("</main>")
    if a < 0 or z < a:
        return html
    page = re.sub(r'<section id="[^"]+"[^>]*\shidden[\s>][\s\S]*?</section>', "", html[a:z])
    page = re.sub(r'<a hidden [^>]*>[^<]*</a>', "", page)
    return html[:a] + page + html[z:]


def check(html: str) -> list:
    problems = []
    if len(html) < 100_000:
        problems.append(f"too small ({len(html)} bytes)")
    for must in ('id="site-state"', 'className+=" fk-wait"', LIVE_KIT, "</html>", 'property="og:image"', 'rel="icon"'):
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

    html = prune(make_live(asyncio.run(build(pathlib.Path(a.studio), draft))))
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
