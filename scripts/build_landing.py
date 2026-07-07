#!/usr/bin/env python3
"""Build the GitHub Pages site (docs/) from the canonical markdown.

Renders the essay and the About page into self-contained, dependency-free
editorial HTML that shares one nav, stylesheet, and theme toggle. The essay
markdown stays the single source of truth. Re-run after editing either file:

    python scripts/build_landing.py

GitHub Pages serves the `docs/` folder: docs/index.html is the home (the essay),
docs/about.html is "How this was made", docs/explore/ is the interactive page.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/Kirill-Kruglov/justitia"


def pandoc(md_path):
    return subprocess.run(
        ["pandoc", str(md_path), "-t", "html", "--no-highlight"],
        capture_output=True, text=True, check=True,
    ).stdout


def toc_from(body):
    heads = re.findall(r'<h([12]) id="([^"]+)">(.*?)</h[12]>', body, re.DOTALL)
    items, first_h1 = [], False
    for level, hid, text in heads:
        text = re.sub(r"<[^>]+>", "", text).strip()
        if level == "1" and not first_h1:
            first_h1 = True
            continue
        cls = "toc-h1" if level == "1" else "toc-h2"
        items.append(f'<a class="{cls}" href="#{hid}">{text}</a>')
    return "\n".join(items)


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
.byline{margin:18px 0 0;font-family:system-ui,sans-serif;font-size:14px;color:var(--muted)}
.byline a{color:var(--muted);text-decoration:underline;text-underline-offset:2px}
.byline a:hover{color:var(--ink)}
h1{font-size:clamp(34px,6vw,52px);line-height:1.08;letter-spacing:-.01em;margin:48px 0 8px}
h2{font-size:26px;line-height:1.2;margin:52px 0 6px}
p{margin:0 0 20px}
a{color:var(--accent);text-decoration:underline;text-underline-offset:2px;text-decoration-thickness:.5px}
strong{font-weight:700}
hr{border:0;border-top:1px solid var(--rule);margin:44px 0}
blockquote{margin:28px 0;padding:2px 0 2px 20px;border-left:3px solid var(--line);color:var(--muted);font-size:18px}
blockquote p{margin:0 0 10px}
table{width:100%;border-collapse:collapse;margin:24px 0;font-size:15.5px;font-family:system-ui,sans-serif}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
thead th{background:var(--tablehead);border-bottom:2px solid var(--line);font-weight:600}
td:nth-child(n+3),th:nth-child(n+3){text-align:right;font-variant-numeric:tabular-nums}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86em;
  background:color-mix(in srgb,var(--ink) 7%,transparent);padding:.1em .35em;border-radius:4px}
.contents{margin:34px 0 8px;border:1px solid var(--line);border-radius:10px;
  font-family:system-ui,sans-serif;font-size:15px}
.contents summary{cursor:pointer;padding:5px 18px;color:var(--muted);font-weight:600;list-style:none}
.contents summary::-webkit-details-marker{display:none}
.contents summary::before{content:"\\203A";display:inline-block;padding-right:7px;transition:transform .15s}
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

NAV = """<nav class="nav">
  <a class="brand" href="./">justitia</a>
  <div class="right">
    <a href="./">Essay</a>
    <a href="explore/">Explorable</a>
    <a href="about.html">About</a>
    <a href="REPO">GitHub</a>
    <button id="theme" type="button" aria-label="Toggle light / dark">&#9682;</button>
  </div>
</nav>""".replace("REPO", REPO)

THEME_JS = """<script>
(function(){
  var root=document.documentElement, KEY="justitia-theme";
  var saved=localStorage.getItem(KEY);
  if(saved) root.setAttribute("data-theme",saved);
  document.getElementById("theme").addEventListener("click",function(){
    var cur=root.getAttribute("data-theme");
    if(!cur) cur=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
    var next=cur==="dark"?"light":"dark";
    root.setAttribute("data-theme",next);
    localStorage.setItem(KEY,next);
  });
})();
</script>"""

FOOTER = f"""<footer>
  <p><strong>justitia</strong> — code, data, tests, and the interactive version:
  <a href="{REPO}">github.com/Kirill-Kruglov/justitia</a>.
  A response to Dario Amodei's <a href="https://www.darioamodei.com/essay/machines-of-loving-grace">Machines of Loving Grace</a>.</p>
</footer>"""

BYLINE = ('<p class="byline">By Kirill Kruglov, developed in dialogue with Claude, Codex, and Fable'
          ' — <a href="about.html">how this was made</a>.</p>')


def page(title, description, body, *, contents="", byline=""):
    head = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{description}">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{description}">\n'
        '<meta property="og:type" content="article">\n'
        f"<style>{CSS}</style>\n"
        '<script>try{var t=localStorage.getItem("justitia-theme");'
        'if(t)document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>\n'
        "</head>\n<body>\n"
    )
    main = f'<main id="top">\n{byline}\n{contents}\n<article>\n{body}\n</article>\n</main>\n'
    return head + NAV + "\n" + main + FOOTER + "\n" + THEME_JS + "\n</body>\n</html>\n"


def main():
    DOCS.mkdir(exist_ok=True)
    essay = pandoc(ROOT / "essay" / "soil-for-seeds-of-loving-grace.md")
    contents = (f'<details class="contents">\n<summary>Contents</summary>\n'
                f'<nav>\n{toc_from(essay)}\n</nav>\n</details>')
    (DOCS / "index.html").write_text(page(
        "Soil for Seeds of Loving Grace",
        "What kind of world would let a powerful, well-meaning AI keep doing good? "
        "A blind-governance simulation, and a counterpoint to Machines of Loving Grace.",
        essay, contents=contents, byline=BYLINE,
    ), encoding="utf-8")
    about = pandoc(ROOT / "essay" / "about.md")
    (DOCS / "about.html").write_text(page(
        "How this was made — justitia",
        "How justitia was built: one person in adversarial dialogue with Claude and Codex.",
        about,
    ), encoding="utf-8")
    print(f"wrote {DOCS/'index.html'} and {DOCS/'about.html'}")


if __name__ == "__main__":
    main()
