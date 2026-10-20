#!/usr/bin/env python3
"""Build index.html from the Fabrik 2.5 Studio.

usage: export25.py --studio <studio.html> --draft <draft.json> [--out index.html]

The Studio page is opened headlessly with the draft injected into localStorage
(the Studio's no-db fallback), then window.FabrikStudioBuild() returns the page
exactly as the Studio's Download button would. Exit 3 when the output matches the
current file; exit 1 on any error or an export that looks incomplete.
"""
import argparse, json, os, sys, asyncio

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--studio', required=True)
    ap.add_argument('--draft', required=True)
    ap.add_argument('--out', default='index.html')
    a = ap.parse_args()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print('playwright missing: pip install playwright && playwright install chromium', file=sys.stderr); return 1
    draft = open(a.draft, encoding='utf-8').read()
    d = json.loads(draft)
    if 'state' not in d: d = {'state': d, 'updatedAt': 0}; draft = json.dumps(d)

    async def run():
        async with async_playwright() as p:
            b = await p.chromium.launch(); ctx = await b.new_context()
            await ctx.add_init_script("try{localStorage.setItem('fabrik25Draft'," + json.dumps(draft) + ")}catch(e){}")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('file://' + os.path.abspath(a.studio)); await pg.wait_for_timeout(1500)
            html = await pg.evaluate('window.FabrikStudioBuild()')
            await b.close()
            return html, errs
    html, errs = asyncio.run(run())
    if errs: print('studio errors: ' + '; '.join(errs), file=sys.stderr); return 1
    checks = ['<section id="hero"', '<section id="contact"', '<footer', 'og:image', 'site-state', 'FabrikMoire']
    missing = [c for c in checks if c not in html]
    if missing or len(html) < 60000: print('export looks incomplete: ' + ', '.join(missing), file=sys.stderr); return 1
    if 'FABRIK_EDITOR=1' in html: print('export carries the editor flag', file=sys.stderr); return 1
    if os.path.exists(a.out) and open(a.out, encoding='utf-8').read() == html: return 3
    open(a.out, 'w', encoding='utf-8').write(html)
    print('wrote %s (%d bytes)' % (a.out, len(html))); return 0

if __name__ == '__main__': sys.exit(main())
