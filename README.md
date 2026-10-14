# Fabrik Collective site

Static export of the Fabrik Site Studio draft. `index.html` is the whole site (styles, renderer and content inline).

- Edit content in the Studio, then export and replace `index.html`.
- Fonts: Adobe Fonts kit cib4apc ("Fabrik Collective · live site": marcschaad.github.io, fabrikcollective.com, www, localhost). The Studio draft carries kit psd4mxj; swap it for cib4apc at export. Claude artifacts block Adobe Fonts, so the Studio preview never shows Arsenica: judge type here, on staging.
- Live: served at fabrikcollective.com (CNAME file). No `noindex`; `robots.txt` allows all. Keep the CNAME file on every export, and do not re-add `noindex` at export.
