# Fabrik Collective site

Static export of the Fabrik Site Studio draft. `index.html` is the whole site (styles, renderer and content inline).

- Edit content in the Studio, then press **Export to site** (two clicks: it asks first). That fires the "Push Fabrik site" scheduled task, which reads the Studio and its draft, runs `tools/export_site.py`, and commits and pushes `index.html`. Progress shows in the Studio bar (from the Studio's `site/publish` document). **Download** in the Studio still saves the file by hand.
- `tools/export_site.py --studio <studio.html> --draft <draft.json>` builds `index.html` exactly as the Studio would download it, then swaps the font kit to cib4apc and strips any noindex. It refuses to write an export that looks incomplete. Exit 3 means nothing changed.
- Fonts: Adobe Fonts kit cib4apc ("Fabrik Collective · live site": marcschaad.github.io, fabrikcollective.com, www, localhost). The Studio draft carries kit psd4mxj; swap it for cib4apc at export. Claude artifacts block Adobe Fonts, so the Studio preview never shows Arsenica: judge type here, on staging.
- Live: served at fabrikcollective.com (CNAME file). No `noindex`; `robots.txt` allows all. Keep the CNAME file on every export, and do not re-add `noindex` at export.
