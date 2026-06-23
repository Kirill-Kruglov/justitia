#!/usr/bin/env python3
"""Build the GitHub Pages landing (index.html) from the canonical essay.

The essay markdown stays the single source of truth; this renders it into a
self-contained, dependency-free editorial page (top nav, collapsible contents,
light/dark toggle). Re-run after editing the essay:

    python scripts/build_landing.py
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ESSAY = ROOT / "essay" / "soil-for-seeds-of-loving-grace.md"
OUT = ROOT / "index.html"

body = subprocess.run(
    ["pandoc", str(ESSAY), "-t", "html", "--no-highlight"],
    capture_output=True, text=True, check=True,
).stdout

# Build a two-part table of contents from the headers (skip the title h1).
heads = re.findall(r'<h([12]) id="([^"]+)">(.*?)</h[12]>', body, re.DOTALL)
toc = []
first_h1_seen = False
for level, hid, text in heads:
    text = re.sub(r"<[^>]+>", "", text).strip()
    if level == "1" and not first_h1_seen:
        first_h1_seen = True
        continue  # the title itself
    cls = "toc-h1" if level == "1" else "toc-h2"
    toc.append(f'<a class="{cls}" href="#{hid}">{text}</a>')
toc_html = "\n".join(toc)

CSS = """
:root{--bg:#fbfaf6;--ink:#1d1c1a;--muted:#6b6760;--line:#e4e0d6;--accent:#7a5b2e;--rule:#ece8de;--tablehead:#f3f0e8}
:root[data-theme=dark]{--bg:#15171c;--ink:#dfdcd4;--muted:#9a958c;--line:#2a2d34;--accent:#cdb079;--rule:#23262d;--tablehead:#1c1f25}
@media (prefers-color-scheme:dark){:root:not([data-theme]){--bg:#15171c;--ink:#dfdcd4;--muted:#9a958c;--line:#2a2d34;--accent:#cdb079;--rule:#23262d;--tablehead:#1c1f25}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:20px/1.7 Iowan Old Style,Palatino,Georgia,"Times New Roman",serif;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.nav{position:sticky;top:0;z-index:10;display:flex;justify-content:space-between;align-items:center;
  gap:16px;padding:12px clamp(16px,5vw,40px);background:var(--bg);border-bottom:1px solid var(--line);
  font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:15px}
.nav .brand{font-weight:700;letter-spacing:.02em;color:var(--ink);text-decoration:none}
.nav .right{display:flex;align-items:center;gap:18px}
.nav a{color:var(--muted);text-decoration:none}
.nav a:hover{color:var(--ink)}
.nav button{background:none;border:1px solid var(--line);color:var(--muted);border-radius:999px;
  width:34px;height:34px;cursor:pointer;font-size:15px;line-height:1}
.nav button:hover{color:var(--ink)}
main{max-width:680px;margin:0 auto;padding:0 22px 96px}
h1{font-size:clamp(34px,6vw,52px);line-height:1.08;letter-spacing:-.01em;margin:48px 0 8px}
h2{font-size:26px;line-height:1.2;margin:52px 0 6px}
p{margin:0 0 20px}
a{color:var(--accent);text-decoration:underline;text-underline-offset:2px;text-decoration-thickness:.5px}
strong{font-weight:700}
hr{border:0;border-top:1px solid var(--rule);margin:44px 0}
blockquote{margin:28px 0;padding:2px 0 2px 20px;border-left:3px solid var(--line);color:var(--muted);font-size:18px}
blockquote p{margin:0 0 10px}
table{width:100%;border-collapse:collapse;margin:24px 0;font-size:15.5px;
  font-family:system-ui,sans-serif}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
thead th{background:var(--tablehead);border-bottom:2px solid var(--line);font-weight:600}
td:nth-child(n+3),th:nth-child(n+3){text-align:right;font-variant-numeric:tabular-nums}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86em;
  background:color-mix(in srgb,var(--ink) 7%,transparent);padding:.1em .35em;border-radius:4px}
.contents{margin:40px 0 8px;border:1px solid var(--line);border-radius:10px;
  font-family:system-ui,sans-serif;font-size:15px}
.contents summary{cursor:pointer;padding:12px 16px;color:var(--muted);font-weight:600;list-style:none}
.contents summary::-webkit-details-marker{display:none}
.contents summary::before{content:"\\203A  ";display:inline-block;transition:transform .15s}
.contents[open] summary::before{transform:rotate(90deg)}
.contents nav{display:flex;flex-direction:column;padding:0 16px 14px}
.contents a{color:var(--muted);text-decoration:none;padding:4px 0}
.contents a:hover{color:var(--ink)}
.contents .toc-h1{color:var(--ink);font-weight:700;margin-top:10px}
.contents .toc-h2{padding-left:16px}
footer{max-width:680px;margin:0 auto;padding:28px 22px 64px;border-top:1px solid var(--rule);
  color:var(--muted);font-family:system-ui,sans-serif;font-size:14px}
footer a{color:var(--muted)}
"""

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Soil for Seeds of Loving Grace</title>
<meta name="description" content="What kind of world would let a powerful, well-meaning AI keep doing good? A blind-governance simulation, and a counterpoint to Machines of Loving Grace.">
<meta property="og:title" content="Soil for Seeds of Loving Grace">
<meta property="og:description" content="Blind governance, simulated: the only thing that holds is consequence-gated anti-concentration. A counterpoint to Machines of Loving Grace.">
<meta property="og:type" content="article">
<style>{CSS}</style>
</head>
<body>
<nav class="nav">
  <a class="brand" href="./">justitia</a>
  <div class="right">
    <a href="#top">Essay</a>
    <a href="web/">Explorable</a>
    <a href="https://github.com/Kirill-Kruglov/justitia">GitHub</a>
    <button id="theme" type="button" aria-label="Toggle light / dark">&#9682;</button>
  </div>
</nav>
<main id="top">
  <details class="contents">
    <summary>Contents</summary>
    <nav>
{toc_html}
    </nav>
  </details>
  <article>
{body}
  </article>
</main>
<footer>
  <p><strong>justitia</strong> — code, data, tests, and the interactive version:
  <a href="https://github.com/Kirill-Kruglov/justitia">github.com/Kirill-Kruglov/justitia</a>.
  A response to Dario Amodei's <a href="https://www.darioamodei.com/essay/machines-of-loving-grace">Machines of Loving Grace</a>.</p>
</footer>
<script>
(function(){{
  var root=document.documentElement, KEY="justitia-theme";
  var saved=localStorage.getItem(KEY);
  if(saved) root.setAttribute("data-theme",saved);
  document.getElementById("theme").addEventListener("click",function(){{
    var cur=root.getAttribute("data-theme");
    if(!cur) cur=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
    var next=cur==="dark"?"light":"dark";
    root.setAttribute("data-theme",next);
    localStorage.setItem(KEY,next);
  }});
}})();
</script>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT} ({len(HTML)} bytes, {len(toc)} TOC entries)")
