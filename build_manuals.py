#!/usr/bin/env python3
"""
build_manuals.py
Converts sDoc DOCX manuals into a self-contained HTML portal.

Usage:
    python build_manuals.py
    python build_manuals.py --input "path/to/docx" --output "path/to/docs"
"""

import os
import re
import sys
import argparse
import mammoth
from bs4 import BeautifulSoup, NavigableString
from pathlib import Path

try:
    from videos_config import VIDEOS
except ImportError:
    VIDEOS = []

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INPUT = r"c:\Users\grana\Downloads\files (1)\files"
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# Icon overrides: keyword (lowercase) → emoji.
# The script picks the first keyword found in the filename.
# Add new keywords here as needed; unknown files get 📋.
ICON_RULES = [
    ("usuario",       "👤"),
    ("login",         "🔑"),
    ("empresa",       "🏢"),
    ("membro",        "👥"),
    ("configurac",    "⚙️"),
    ("solicitac",     "📄"),
    ("api",           "🔗"),
    ("automatico",    "🤖"),
    ("explorando",    "🗺️"),
    ("relatorio",     "📊"),
    ("pagamento",     "💳"),
    ("certificado",   "🏅"),
    ("notificac",     "🔔"),
    ("permissao",     "🛡️"),
    ("webhook",       "⚡"),
]


def guess_icon(filename: str) -> str:
    """Pick an emoji icon based on keywords in the filename."""
    lower = filename.lower()
    for keyword, icon in ICON_RULES:
        if keyword in lower:
            return icon
    return "📋"


def slugify(filename: str) -> str:
    """Convert a DOCX filename to a clean HTML output name."""
    stem = Path(filename).stem                         # e.g. Manual_10_Relatorio
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower())   # manual-10-relatorio
    slug = slug.strip("-")
    return slug + ".html"


def extract_num(filename: str) -> str:
    """Extract leading number from filename, e.g. 'Manual_10_...' → '10'."""
    m = re.search(r"(\d+)", filename)
    return m.group(1).zfill(2) if m else "00"


def discover_manuals(input_dir: Path) -> list[tuple[str, str, str, str]]:
    """
    Scan input_dir for .docx files and return sorted list of
    (docx_filename, output_html_name, icon, display_num).
    Sorted by the leading number in the filename.
    """
    docx_files = sorted(
        input_dir.glob("*.docx"),
        key=lambda p: extract_num(p.name)
    )
    result = []
    for path in docx_files:
        name = path.name
        result.append((
            name,
            slugify(name),
            guess_icon(name),
            extract_num(name),
        ))
    return result

# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

CSS = """
  :root {
    --primary: #7B2FBE;
    --primary-dark: #1C0740;
    --primary-light: #F3E8FF;
    --accent: #9333EA;
    --text: #1a1a2e;
    --text-muted: #6E5F85;
    --border: #E5D6F7;
    --bg: #FAF5FF;
    --white: #ffffff;
    --step-bg: #F0E6FA;
    --obs-bg: #fff8e1;
    --obs-border: #f59e0b;
    --success: #059669;
    --shadow: 0 2px 12px rgba(123,47,190,.10);
    --shadow-md: 0 4px 24px rgba(123,47,190,.15);
    --radius: 10px;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.7;
    color: var(--text);
    background: var(--bg);
  }

  /* ---- TOP BAR ---- */
  .topbar {
    position: sticky; top: 0; z-index: 100;
    background: var(--primary-dark);
    color: #fff;
    display: flex; align-items: center; gap: 12px;
    padding: 0 24px;
    height: 52px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25);
  }
  .topbar-logo { font-weight: 700; font-size: 1.15rem; letter-spacing: -.5px; color: #fff; text-decoration: none; }
  .topbar-logo span { color: #C4B5FD; }
  .topbar-sep { color: #C4B5FD; font-size: .85rem; }
  .topbar-title { font-size: .9rem; color: #DDD6FE; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .topbar-back {
    margin-left: auto;
    background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.2);
    color: #fff;
    font-size: .8rem;
    padding: 5px 14px;
    border-radius: 6px;
    text-decoration: none;
    white-space: nowrap;
    transition: background .15s;
  }
  .topbar-back:hover { background: rgba(255,255,255,.22); }

  /* ---- LAYOUT ---- */
  .layout { display: flex; min-height: calc(100vh - 52px); }

  /* ---- SIDEBAR ---- */
  .sidebar {
    width: 260px; flex-shrink: 0;
    background: var(--white);
    border-right: 1px solid var(--border);
    padding: 24px 0;
    position: sticky; top: 52px;
    height: calc(100vh - 52px);
    overflow-y: auto;
  }
  .sidebar-heading {
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 0 20px 10px;
  }
  .sidebar ul { list-style: none; }
  .sidebar ul li a {
    display: block;
    padding: 7px 20px 7px 24px;
    font-size: .85rem;
    color: var(--text-muted);
    text-decoration: none;
    border-left: 3px solid transparent;
    transition: all .15s;
    line-height: 1.4;
  }
  .sidebar ul li a:hover { color: var(--primary); background: var(--primary-light); }
  .sidebar ul li a.active { color: var(--primary); border-left-color: var(--primary); background: var(--primary-light); font-weight: 600; }
  .sidebar-divider { margin: 12px 20px; border: none; border-top: 1px solid var(--border); }

  /* ---- MAIN CONTENT ---- */
  .main { flex: 1; min-width: 0; }
  .content {
    max-width: 860px;
    margin: 0 auto;
    padding: 40px 36px 80px;
  }

  /* ---- MANUAL HEADER ---- */
  .manual-header { margin-bottom: 32px; }
  .manual-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--primary-light);
    color: var(--primary);
    font-size: .75rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 12px;
  }
  .manual-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--primary-dark);
    line-height: 1.25;
    margin-bottom: 6px;
  }
  .manual-subtitle {
    font-size: 1rem;
    color: var(--text-muted);
    margin-bottom: 20px;
  }

  /* ---- VERSION TABLE ---- */
  .version-table {
    display: flex; gap: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 28px;
    background: var(--white);
  }
  .version-cell {
    flex: 1;
    padding: 12px 16px;
    border-right: 1px solid var(--border);
  }
  .version-cell:last-child { border-right: none; }
  .version-label { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--text-muted); margin-bottom: 3px; }
  .version-value { font-size: .95rem; font-weight: 600; color: var(--text); }

  /* ---- INTRO ---- */
  .intro {
    background: var(--white);
    border: 1px solid var(--border);
    border-left: 4px solid var(--primary);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 16px 20px;
    color: var(--text);
    margin-bottom: 36px;
    font-size: .95rem;
  }

  /* ---- SECTION HEADING ---- */
  .section-heading {
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--primary-dark);
    margin: 36px 0 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
    scroll-margin-top: 70px;
  }

  /* ---- STEP BLOCK ---- */
  .step {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 24px;
    overflow: hidden;
    scroll-margin-top: 70px;
  }
  .step-header {
    display: flex; align-items: center; gap: 14px;
    background: var(--step-bg);
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
  }
  .step-num {
    width: 30px; height: 30px; flex-shrink: 0;
    background: var(--primary);
    color: #fff;
    font-size: .8rem;
    font-weight: 700;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
  }
  .step-title { font-size: 1rem; font-weight: 600; color: var(--primary-dark); line-height: 1.3; }
  .step-body { padding: 18px 20px; }
  .step-body p { margin-bottom: 12px; }
  .step-body p:last-child { margin-bottom: 0; }
  .step-body strong { color: var(--primary-dark); }

  /* ---- FIGURES ---- */
  figure {
    margin: 18px 0;
    text-align: center;
  }
  figure img {
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
  }
  figcaption {
    margin-top: 7px;
    font-size: .8rem;
    color: var(--text-muted);
    font-style: italic;
  }

  /* ---- OBS BOX ---- */
  .obs-box {
    background: var(--obs-bg);
    border: 1px solid var(--obs-border);
    border-left: 4px solid var(--obs-border);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 12px 16px;
    font-size: .9rem;
    margin: 14px 0;
  }
  .obs-box strong { color: #92400e; }

  /* ---- SUPPORT SECTION ---- */
  .support-section {
    margin-top: 48px;
    padding-top: 28px;
    border-top: 2px solid var(--border);
  }
  .support-title { font-size: 1rem; font-weight: 700; color: var(--text-muted); margin-bottom: 16px; text-transform: uppercase; letter-spacing: .06em; font-size: .8rem; }
  .support-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
  .support-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px;
  }
  .support-card h4 { font-size: .9rem; color: var(--primary-dark); margin-bottom: 10px; }
  .support-card p { font-size: .85rem; color: var(--text-muted); margin-bottom: 6px; line-height: 1.5; }

  /* ---- BODY CONTENT (outside steps) ---- */
  .body-content p { margin-bottom: 12px; font-size: .95rem; }
  .body-content strong { color: var(--primary-dark); }
  .body-content em { color: var(--text-muted); }
  .body-content ul, .body-content ol { margin: 8px 0 12px 24px; }
  .body-content li { margin-bottom: 4px; font-size: .95rem; }

  /* ---- NUMBERED LIST ITEMS ---- */
  .numbered-item { display: flex; gap: 10px; margin-bottom: 10px; }
  .numbered-item-num { font-weight: 700; color: var(--primary); min-width: 20px; }

  /* ---- PREV/NEXT NAV ---- */
  .page-nav {
    display: flex; gap: 12px; justify-content: space-between;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
  }
  .page-nav a {
    display: flex; align-items: center; gap: 8px;
    padding: 12px 20px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    text-decoration: none;
    color: var(--primary);
    font-size: .85rem;
    font-weight: 600;
    background: var(--white);
    transition: all .15s;
    max-width: 48%;
  }
  .page-nav a:hover { background: var(--primary-light); border-color: var(--primary); }
  .page-nav .next { margin-left: auto; flex-direction: row-reverse; }
  .page-nav .prev-label, .page-nav .next-label { font-size: .75rem; font-weight: 400; color: var(--text-muted); display: block; }

  /* ---- INDEX STYLES ---- */
  .index-hero {
    background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
    color: #fff;
    padding: 56px 40px;
    text-align: center;
  }
  .index-hero h1 { font-size: 2.2rem; font-weight: 800; margin-bottom: 10px; }
  .index-hero p { font-size: 1.05rem; opacity: .85; max-width: 600px; margin: 0 auto; }
  .index-body { max-width: 1080px; margin: 0 auto; padding: 48px 24px 80px; }
  .index-section-title { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-muted); margin-bottom: 20px; }
  .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
  .card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    text-decoration: none;
    color: var(--text);
    display: block;
    transition: all .18s;
    box-shadow: var(--shadow);
  }
  .card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); border-color: var(--primary); }
  .card-top { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
  .card-icon { font-size: 1.7rem; width: 44px; text-align: center; }
  .card-num { font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--primary); background: var(--primary-light); padding: 3px 9px; border-radius: 12px; }
  .card-title { font-size: 1rem; font-weight: 700; color: var(--primary-dark); margin-bottom: 6px; line-height: 1.3; }
  .card-subtitle { font-size: .83rem; color: var(--text-muted); line-height: 1.45; }
  .card-arrow { margin-top: 16px; font-size: .8rem; color: var(--primary); font-weight: 600; }

  /* ---- VIDEOS PAGE ---- */
  .video-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 28px;
    margin-top: 8px;
  }
  .video-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
    transition: box-shadow .18s;
  }
  .video-card:hover { box-shadow: var(--shadow-md); }
  .video-embed {
    position: relative;
    width: 100%;
    padding-top: 56.25%;
    background: #0a0012;
  }
  .video-embed iframe {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    border: none;
  }
  .video-info { padding: 18px 20px; }
  .video-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .video-icon { font-size: 1.3rem; }
  .video-label {
    font-size: .68rem; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; color: var(--primary);
    background: var(--primary-light); padding: 2px 8px; border-radius: 10px;
  }
  .video-title { font-size: 1rem; font-weight: 700; color: var(--primary-dark); margin-bottom: 6px; line-height: 1.3; }
  .video-desc { font-size: .85rem; color: var(--text-muted); line-height: 1.5; }
  .video-tags { margin-top: 12px; display: flex; gap: 6px; flex-wrap: wrap; }
  .video-tag {
    font-size: .72rem; color: var(--text-muted);
    background: var(--bg); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 10px;
  }

  /* ---- RESPONSIVE ---- */
  @media (max-width: 768px) {
    .sidebar { display: none; }
    .content { padding: 24px 16px 60px; }
    .manual-title { font-size: 1.4rem; }
    .version-table { flex-direction: column; }
    .version-cell { border-right: none; border-bottom: 1px solid var(--border); }
    .version-cell:last-child { border-bottom: none; }
    .page-nav { flex-direction: column; }
    .page-nav a { max-width: 100%; }
    .index-hero { padding: 36px 20px; }
    .index-hero h1 { font-size: 1.6rem; }
    .index-body { padding: 28px 16px 60px; }
  }
"""

# ---------------------------------------------------------------------------
# HTML Helpers
# ---------------------------------------------------------------------------

def make_html_page(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{CSS}</style>
  {extra_head}
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Document Processing
# ---------------------------------------------------------------------------

def is_bold_only(tag) -> bool:
    """True if a <p> contains only bold content (strong or em with all text in strong)."""
    if tag.name != "p":
        return False
    texts = [t for t in tag.strings if t.strip()]
    if not texts:
        return False
    strong_texts = [t for t in tag.find_all("strong") for t in [t.get_text()]]
    all_text = "".join(texts)
    bold_text = "".join(strong_texts)
    return len(bold_text.strip()) > 0 and len(bold_text.strip()) >= len(all_text.strip()) * 0.85


def extract_version_table(table_tag) -> dict | None:
    """Detect and parse the Version/Date/Responsible table."""
    rows = table_tag.find_all("tr")
    if not rows:
        return None
    header_row = rows[0]
    headers = [td.get_text(strip=True).lower() for td in header_row.find_all("td")]
    if not any("vers" in h for h in headers):
        return None
    if len(rows) < 2:
        return None
    data_row = rows[1]
    cells = [td.get_text(strip=True) for td in data_row.find_all("td")]
    return {
        "version": cells[0] if len(cells) > 0 else "",
        "date":    cells[1] if len(cells) > 1 else "",
        "author":  cells[2] if len(cells) > 2 else "",
    }


def is_obs_table(table_tag) -> bool:
    """True if table is a single-cell OBS note."""
    tds = table_tag.find_all("td")
    if len(tds) != 1:
        return False
    return "obs" in tds[0].get_text(strip=True).lower()[:10]


def is_support_table(table_tag) -> bool:
    """True if table contains support contact info."""
    text = table_tag.get_text(strip=True).lower()
    return any(kw in text for kw in ["suporte", "atendimento", "0800", "plurio", "safeweb"])


def parse_step_number(text: str) -> str | None:
    """Extract step number from 'Passo N ...' or return None."""
    m = re.match(r"passo\s+(\d+)", text.strip(), re.IGNORECASE)
    return m.group(1) if m else None


def render_support_table(table_tag) -> str:
    """Convert support table into support card grid HTML."""
    cards_html = ""
    for td in table_tag.find_all("td"):
        inner = ""
        for el in td.children:
            if isinstance(el, NavigableString):
                t = str(el).strip()
                if t:
                    inner += f"<p>{t}</p>"
            elif el.name == "p":
                inner += f"<p>{el.decode_contents()}</p>"
        if inner.strip():
            cards_html += f'<div class="support-card">{inner}</div>'
    return f'<div class="support-grid">{cards_html}</div>' if cards_html else ""


def convert_docx(docx_path: str, out_filename: str, num: str, icon: str,
                  prev_info: tuple | None, next_info: tuple | None) -> tuple[str, str, str]:
    """
    Convert a DOCX file to a complete HTML manual page.
    Returns (html_string, title, subtitle).
    """
    with open(docx_path, "rb") as f:
        result = mammoth.convert_to_html(f)
    raw_html = result.value

    soup = BeautifulSoup(raw_html, "html.parser")
    elements = list(soup.children)

    title = ""
    subtitle = ""
    version_info = None
    intro = ""
    toc_items = []         # [(anchor_id, label), ...]
    body_blocks = []       # list of HTML strings
    support_html = ""

    # --- Pass 1: extract title, subtitle, version table, intro ---
    idx = 0
    while idx < len(elements):
        el = elements[idx]
        if isinstance(el, NavigableString):
            idx += 1
            continue

        # Title: first bold-only paragraph
        if not title and el.name == "p" and is_bold_only(el):
            title = el.get_text(strip=True)
            idx += 1
            continue

        # Subtitle: second plain paragraph (right after title)
        if title and not subtitle and el.name == "p" and not is_bold_only(el):
            text = el.get_text(strip=True)
            if text and "<img" not in str(el):
                subtitle = text
                idx += 1
                continue

        # Version table
        if not version_info and el.name == "table":
            version_info = extract_version_table(el)
            if version_info:
                idx += 1
                continue

        # Intro: first content paragraph after version table
        if version_info and not intro and el.name == "p":
            text = el.get_text(strip=True)
            if text and not is_bold_only(el) and "<img" not in str(el):
                intro = el.decode_contents()  # preserves spaces around <strong> tags
                idx += 1
                continue

        break  # everything else goes to body

    # --- Pass 2: process body elements into blocks ---
    current_step_body = []
    current_step_num = None
    current_step_title = ""
    in_step = False
    section_counter = 0

    def flush_step():
        nonlocal in_step, current_step_body, current_step_num, current_step_title
        if in_step:
            body_html = "\n".join(current_step_body)
            body_blocks.append(
                f'<div class="step" id="step-{current_step_num}">'
                f'<div class="step-header">'
                f'<span class="step-num">{current_step_num}</span>'
                f'<span class="step-title">{current_step_title}</span>'
                f'</div>'
                f'<div class="step-body body-content">{body_html}</div>'
                f'</div>'
            )
            in_step = False
            current_step_body = []
            current_step_num = None
            current_step_title = ""

    while idx < len(elements):
        el = elements[idx]
        idx += 1

        if isinstance(el, NavigableString):
            continue

        # Support table → goes to support section
        if el.name == "table" and is_support_table(el):
            flush_step()
            support_html = render_support_table(el)
            continue

        # OBS table → inline obs box
        if el.name == "table" and is_obs_table(el):
            td = el.find("td")
            flush_step()
            obs_content = td.decode_contents() if td else ""
            block = f'<div class="obs-box">{obs_content}</div>'
            if in_step:
                current_step_body.append(block)
            else:
                body_blocks.append(block)
            continue

        # Regular table → render as-is inside current context
        if el.name == "table":
            flush_step()
            body_blocks.append(f'<div class="body-content">{str(el)}</div>')
            continue

        # Bold-only paragraph → potential section heading or step header
        if el.name == "p" and is_bold_only(el):
            text = el.get_text(strip=True)
            step_num = parse_step_number(text)

            if step_num:
                flush_step()
                # Step title: remove "Passo N  " prefix
                step_title = re.sub(r"^passo\s+\d+\s*", "", text, flags=re.IGNORECASE).strip()
                toc_items.append((f"step-{step_num}", f"Passo {step_num} — {step_title}"))
                current_step_num = step_num
                current_step_title = step_title
                in_step = True
                continue

            # Section heading (not a step)
            flush_step()
            # Skip generic "Passo a Passo" headers (they're implied by step structure)
            if re.match(r"^passo\s+a\s+passo$", text, re.IGNORECASE):
                continue

            section_counter += 1
            anchor = f"section-{section_counter}"
            toc_items.append((anchor, text))
            body_blocks.append(
                f'<h2 class="section-heading" id="{anchor}">{text}</h2>'
            )
            continue

        # Image paragraph → figure + check if next sibling is caption
        if el.name == "p" and el.find("img"):
            img_tag = el.find("img")
            img_html = str(img_tag)
            # Check if next element is a caption (<p><em>...</em></p>)
            caption = ""
            if idx < len(elements):
                next_el = elements[idx]
                if (not isinstance(next_el, NavigableString) and
                        next_el.name == "p" and next_el.find("em") and
                        not next_el.find("strong") and not next_el.find("img")):
                    cap_text = next_el.get_text(strip=True)
                    if cap_text:
                        caption = f"<figcaption>{cap_text}</figcaption>"
                        idx += 1

            figure = f"<figure>{img_html}{caption}</figure>"
            if in_step:
                current_step_body.append(figure)
            else:
                body_blocks.append(figure)
            continue

        # Caption without preceding image (skip if already consumed above)
        if el.name == "p" and el.find("em") and not el.find("strong") and not el.find("img"):
            text = el.get_text(strip=True)
            if text:
                block = f"<p><em>{text}</em></p>"
                if in_step:
                    current_step_body.append(block)
                else:
                    body_blocks.append(block)
            continue

        # Regular paragraph
        if el.name == "p":
            inner = el.decode_contents().strip()
            if not inner:
                continue
            # Detect "1.  **text**" pattern (numbered list items from DOCX)
            m = re.match(r"^(<strong>(\d+)\.\s*</strong>)(.*)", inner)
            if m:
                num_label = m.group(2)
                rest = m.group(3)
                # Clean up ** markdown leftovers
                rest = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rest)
                block = (
                    f'<div class="numbered-item">'
                    f'<span class="numbered-item-num">{num_label}.</span>'
                    f'<span>{rest}</span>'
                    f'</div>'
                )
            else:
                inner = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", inner)
                block = f"<p>{inner}</p>"

            if in_step:
                current_step_body.append(block)
            else:
                body_blocks.append(block)
            continue

        # Other elements
        raw = str(el)
        if in_step:
            current_step_body.append(raw)
        else:
            body_blocks.append(raw)

    flush_step()

    # --- Build sidebar TOC ---
    toc_html = ""
    if toc_items:
        items_html = "".join(
            f'<li><a href="#{aid}">{label}</a></li>'
            for aid, label in toc_items
        )
        toc_html = f"""
<div class="sidebar">
  <div class="sidebar-heading">Neste manual</div>
  <ul>{items_html}</ul>
</div>"""

    # --- Build version bar ---
    version_bar = ""
    if version_info:
        version_bar = f"""
<div class="version-table">
  <div class="version-cell"><div class="version-label">Versão</div><div class="version-value">{version_info['version']}</div></div>
  <div class="version-cell"><div class="version-label">Atualizado em</div><div class="version-value">{version_info['date']}</div></div>
  <div class="version-cell"><div class="version-label">Responsável</div><div class="version-value">{version_info['author']}</div></div>
</div>"""

    # --- Build prev/next nav ---
    prev_link = ""
    next_link = ""
    if prev_info:
        p_file, p_title = prev_info
        prev_link = f'<a href="{p_file}" class="prev">← <span><span class="prev-label">Anterior</span>{p_title}</span></a>'
    if next_info:
        n_file, n_title = next_info
        next_link = f'<a href="{n_file}" class="next"><span><span class="next-label">Próximo</span>{n_title}</span> →</a>'

    page_nav = f'<div class="page-nav">{prev_link}{next_link}</div>' if (prev_link or next_link) else ""

    # --- Support section ---
    support_section = ""
    if support_html:
        support_section = f"""
<div class="support-section">
  <div class="support-title">Canais de Atendimento</div>
  {support_html}
</div>"""

    # --- Assemble page ---
    body_html = "\n".join(body_blocks)
    intro_html = f'<div class="intro">{intro}</div>' if intro else ""

    scroll_spy_js = """
<script>
(function(){
  const links = document.querySelectorAll('.sidebar a');
  const targets = Array.from(links).map(a => document.querySelector(a.getAttribute('href')));
  function onScroll(){
    const mid = window.scrollY + window.innerHeight / 3;
    let active = null;
    targets.forEach((t,i) => { if(t && t.offsetTop <= mid) active = i; });
    links.forEach((a,i) => a.classList.toggle('active', i === active));
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
})();
</script>"""

    page_body = f"""
<div class="topbar">
  <a href="index.html" class="topbar-logo">s<span>Doc</span></a>
  <span class="topbar-sep">/</span>
  <span class="topbar-title">{title}</span>
  <a href="index.html" class="topbar-back">← Todos os manuais</a>
</div>
<div class="layout">
  {toc_html}
  <div class="main">
    <div class="content">
      <div class="manual-header">
        <div class="manual-badge">{icon} Manual {num}</div>
        <h1 class="manual-title">{title}</h1>
        <p class="manual-subtitle">{subtitle}</p>
        {version_bar}
      </div>
      {intro_html}
      <div class="body-content">
        {body_html}
      </div>
      {support_section}
      {page_nav}
    </div>
  </div>
</div>
{scroll_spy_js}"""

    html = make_html_page(f"{title} — sDoc", page_body)
    return html, title, subtitle


# ---------------------------------------------------------------------------
# Index Page
# ---------------------------------------------------------------------------

def build_index(manual_data: list[tuple[str, str, str, str, str]]) -> str:
    """
    Build the portal index page.
    manual_data: list of (filename, title, subtitle, icon, num)
    """
    cards_html = ""
    for filename, title, subtitle, icon, num in manual_data:
        cards_html += f"""
<a href="{filename}" class="card">
  <div class="card-top">
    <div class="card-icon">{icon}</div>
    <div class="card-num">Manual {num}</div>
  </div>
  <div class="card-title">{title}</div>
  <div class="card-subtitle">{subtitle or "Clique para ver o manual completo"}</div>
  <div class="card-arrow">Ver manual →</div>
</a>"""

    videos_card = ""
    if VIDEOS:
        videos_card = f"""
<a href="videos.html" class="card card-videos">
  <div class="card-top">
    <div class="card-icon">🎬</div>
    <div class="card-num" style="background:#2D0A5A;color:#C4B5FD;">Vídeos</div>
  </div>
  <div class="card-title">Tutoriais em Vídeo</div>
  <div class="card-subtitle">{len(VIDEOS)} tutoriais gravados sobre os principais fluxos da plataforma</div>
  <div class="card-arrow">Ver vídeos →</div>
</a>"""

    body = f"""
<div class="topbar">
  <a href="index.html" class="topbar-logo">s<span>Doc</span></a>
  <span class="topbar-sep">/</span>
  <span class="topbar-title">Central de Manuais</span>
</div>
<div class="index-hero">
  <h1>Central de Manuais sDoc</h1>
  <p>Documentação completa da plataforma de assinaturas digitais. Acesse o guia do módulo que você precisa.</p>
</div>
<div class="index-body">
  {f'<div class="index-section-title">Tutoriais</div><div class="cards-grid" style="margin-bottom:36px">{videos_card}</div>' if videos_card else ""}
  <div class="index-section-title">Manuais disponíveis</div>
  <div class="cards-grid">
    {cards_html}
  </div>
</div>"""

    return make_html_page("Central de Manuais — sDoc", body)


# ---------------------------------------------------------------------------
# Videos Page
# ---------------------------------------------------------------------------

def build_videos(videos: list) -> str:
    """Build the videos.html gallery page."""
    if not videos:
        cards_html = "<p>Nenhum vídeo configurado.</p>"
    else:
        cards_html = ""
        for i, v in enumerate(videos, 1):
            drive_id   = v.get("drive_id", "")
            title      = v.get("title", f"Vídeo {i}")
            desc       = v.get("description", "")
            icon       = v.get("icon", "🎬")
            tags       = v.get("tags", [])
            embed_url  = f"https://drive.google.com/file/d/{drive_id}/preview"
            tags_html  = "".join(f'<span class="video-tag">{t}</span>' for t in tags)

            cards_html += f"""
<div class="video-card">
  <div class="video-embed">
    <iframe src="{embed_url}" allow="autoplay" allowfullscreen loading="lazy"></iframe>
  </div>
  <div class="video-info">
    <div class="video-meta">
      <span class="video-icon">{icon}</span>
      <span class="video-label">Vídeo {i:02d}</span>
    </div>
    <div class="video-title">{title}</div>
    <div class="video-desc">{desc}</div>
    {"<div class='video-tags'>" + tags_html + "</div>" if tags else ""}
  </div>
</div>"""

    body = f"""
<div class="topbar">
  <a href="index.html" class="topbar-logo">s<span>Doc</span></a>
  <span class="topbar-sep">/</span>
  <span class="topbar-title">Tutoriais em Vídeo</span>
  <a href="index.html" class="topbar-back">← Todos os manuais</a>
</div>
<div class="index-hero">
  <h1>Tutoriais em Vídeo</h1>
  <p>Assista aos tutoriais gravados sobre os principais fluxos da plataforma sDoc.</p>
</div>
<div class="index-body">
  <div class="index-section-title">{len(videos)} vídeo(s) disponível(is)</div>
  <div class="video-grid">
    {cards_html}
  </div>
</div>"""

    return make_html_page("Tutoriais em Vídeo — sDoc", body)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Converte manuais DOCX do sDoc para HTML.")
    parser.add_argument("--input",  default=DEFAULT_INPUT,  help="Pasta com os arquivos .docx")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Pasta de saída dos HTMLs")
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fonte : {input_dir}")
    print(f"Saída : {output_dir}")
    print()

    manual_data = []  # (filename, title, subtitle, icon, num)

    # Auto-discover all .docx files in input_dir
    discovered = discover_manuals(input_dir)
    if not discovered:
        print(f"  Nenhum arquivo .docx encontrado em: {input_dir}")
        return
    print(f"  {len(discovered)} arquivo(s) encontrado(s):\n")

    # First pass: collect file info
    results = []
    for docx_name, out_name, icon, num in discovered:
        docx_path = input_dir / docx_name
        print(f"  Convertendo {docx_name}...")
        results.append((out_name, icon, num, docx_path))

    # Second pass: build HTML with prev/next links
    # Collect (out_name, title) pairs first
    raw_titles = []
    for item in results:
        if item is None:
            raw_titles.append(None)
            continue
        out_name, icon, num, docx_path = item
        # Quick title extraction
        with open(docx_path, "rb") as f:
            r = mammoth.convert_to_html(f)
        s = BeautifulSoup(r.value, "html.parser")
        first_bold = next(
            (p for p in s.find_all("p") if is_bold_only(p)),
            None
        )
        title = first_bold.get_text(strip=True) if first_bold else out_name
        raw_titles.append((out_name, title))

    # Third pass: build each page
    for i, item in enumerate(results):
        if item is None:
            continue
        out_name, icon, num, docx_path = item

        prev_info = None
        next_info = None
        for j in range(i - 1, -1, -1):
            if raw_titles[j]:
                prev_info = raw_titles[j]
                break
        for j in range(i + 1, len(raw_titles)):
            if raw_titles[j]:
                next_info = raw_titles[j]
                break

        html, title, subtitle = convert_docx(
            str(docx_path), out_name, num, icon, prev_info, next_info
        )

        out_path = output_dir / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        manual_data.append((out_name, title, subtitle, icon, num))
        size_kb = out_path.stat().st_size // 1024
        print(f"  ✓  {out_name}  ({size_kb} KB)")

    # Build videos page
    if VIDEOS:
        videos_html  = build_videos(VIDEOS)
        videos_path  = output_dir / "videos.html"
        with open(videos_path, "w", encoding="utf-8") as f:
            f.write(videos_html)
        print(f"  ✓  videos.html  ({videos_path.stat().st_size // 1024} KB)")

    # Build index
    index_html = build_index(manual_data)
    index_path = output_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"\n  ✓  index.html  ({index_path.stat().st_size // 1024} KB)")
    print(f"\nPronto! Abra:  {index_path}\n")


if __name__ == "__main__":
    main()
