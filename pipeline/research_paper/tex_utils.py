"""
tex_utils.py - LaTeX source file parsing for the research_paper pipeline.

All functions here are zero-API (pure local parsing). They are called by the
individual extractor scripts when the input file is a .tex rather than a PDF.

Key design decisions
--------------------
- Brace-balanced extraction instead of [^}]+ regex, so nested math like
  $\\hat{\\alpha}$ or \\frac{n}{k} is handled correctly.
- \\input{} / \\include{} directives are resolved up to 3 levels deep so
  multi-file papers are handled transparently.
- Comment stripping respects escaped percent signs (\\%).
"""
import re
import os


# ---------------------------------------------------------------------------
# Core I/O helpers
# ---------------------------------------------------------------------------

def strip_comments(content):
    """Remove LaTeX comment text (% to end-of-line), respecting \\%."""
    return re.sub(r'(?<!\\)%[^\n]*', '', content)


def read_tex(tex_path):
    """Read a .tex file and strip comment lines."""
    with open(tex_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    return strip_comments(raw)


def resolve_inputs(content, base_dir, _depth=0):
    """
    Inline \\input{...} / \\include{...} references (up to 3 levels deep).
    Missing files are left as-is.
    """
    if _depth >= 3:
        return content

    def _replace(m):
        fname = m.group(1).strip()
        if not fname.endswith('.tex'):
            fname += '.tex'
        fpath = os.path.join(base_dir, fname)
        if os.path.exists(fpath):
            sub = read_tex(fpath)
            return resolve_inputs(sub, base_dir, _depth + 1)
        return m.group(0)

    return re.sub(r'\\(?:input|include)\{([^}]+)\}', _replace, content)


# ---------------------------------------------------------------------------
# Brace-balanced extractor
# ---------------------------------------------------------------------------

def extract_balanced(content, start):
    """
    Given *content* and *start* pointing at an opening '{', return the text
    inside the matching closing brace, handling arbitrary nesting.
    Returns '' if *start* is not '{'.
    """
    if start >= len(content) or content[start] != '{':
        return ''
    depth, buf, i = 0, [], start
    while i < len(content):
        c = content[i]
        if c == '{':
            if depth > 0:
                buf.append(c)
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return ''.join(buf)
            buf.append(c)
        else:
            buf.append(c)
        i += 1
    return ''.join(buf)  # unclosed - return what we have


# ---------------------------------------------------------------------------
# LaTeX text helpers
# ---------------------------------------------------------------------------

def strip_latex_formatting(s):
    """Strip formatting commands (textbf, emph, etc.) leaving math intact."""
    s = re.sub(
        r'\\(?:textbf|textit|emph|text|textrm|mathrm|mathbf|mathit|mathcal|mathbb)\{([^}]*)\}',
        r'\1', s
    )
    s = re.sub(r'\\(?:hline|cline\{[^}]*\}|toprule|midrule|bottomrule)', '', s)
    s = re.sub(r'\\\\', '', s)
    return s.strip()


def strip_latex_commands(text):
    """
    Strip LaTeX commands to produce readable plain text suitable for NLP.
    Removes figure/table/algorithm environments, command calls, and braces.
    """
    text = re.sub(
        r'\\begin\{(?:figure|table|algorithm|lstlisting|verbatim)[^}]*\}'
        r'.*?\\end\{(?:figure|table|algorithm|lstlisting|verbatim)\}',
        ' ', text, flags=re.DOTALL
    )
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+\*?\s*', ' ', text)
    text = re.sub(r'[{}]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_tex_title(content, fallback='Research Paper'):
    """Extract the paper title from \title{...}."""
    m = re.search(r'\\title\s*\{', content)
    if m:
        title = extract_balanced(content, m.end() - 1)
        title = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', title)
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 3:
            return title
    return fallback


# ---------------------------------------------------------------------------
# Section structure
# ---------------------------------------------------------------------------

_TERMINAL_SECTIONS = re.compile(
    r'^(?:references|bibliography|acknowledgment)', re.IGNORECASE
)


def build_section_map(content):
    """
    Return a list of (char_pos, level, heading) tuples for every
    \\section / \\subsection / \\subsubsection, sorted by position.
    Level: 1=section, 2=subsection, 3=subsubsection.
    """
    sections = []
    for m in re.finditer(r'\\((?:sub)*section)\*?\{', content):
        level = m.group(1).count('sub') + 1
        heading = extract_balanced(content, m.end() - 1)
        heading = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', heading).strip()
        sections.append((m.start(), level, heading))
    return sections


def get_section_at(section_map, pos):
    """Return the heading of the deepest section that starts before *pos*."""
    heading = 'Introduction'
    for sec_pos, _level, sec_heading in section_map:
        if sec_pos <= pos:
            heading = sec_heading
        else:
            break
    return heading


def extract_tex_sections(tex_path):
    """
    Parse a .tex file into sections compatible with parse_pdf_into_sections().

    Returns a list of dicts:
        {"label": str, "raw_text": str, "page_start": 1, "pages_data": []}
    """
    content = read_tex(tex_path)
    base_dir = os.path.dirname(os.path.abspath(tex_path))
    content = resolve_inputs(content, base_dir)

    section_map = build_section_map(content)
    if not section_map:
        return [{'label': 'Full Text',
                 'raw_text': strip_latex_commands(content),
                 'page_start': 1, 'pages_data': []}]

    sections = []
    for i, (pos, level, heading) in enumerate(section_map):
        if _TERMINAL_SECTIONS.match(heading) or level > 2:
            continue
        end_pos = section_map[i + 1][0] if i + 1 < len(section_map) else len(content)
        body = content[pos:end_pos]
        sections.append({
            'label':      heading,
            'raw_text':   strip_latex_commands(body),
            'page_start': 1,
            'pages_data': []
        })
    return sections


# ---------------------------------------------------------------------------
# Notation extraction
# ---------------------------------------------------------------------------

def _extract_nomenclature(content):
    """
    Parse \\nomenclature[opt]{symbol}{description} (nomencl package).
    Uses brace-balanced extraction to handle nested math like $\\hat{\\alpha}$.
    """
    results = []
    cmd_pat = re.compile(r'\\nomenclature\s*(?:\[[^\]]*\])?\s*(?=\{)')
    for m in cmd_pat.finditer(content):
        pos = m.end()
        symbol = extract_balanced(content, pos)
        pos2 = pos + len(symbol) + 2
        while pos2 < len(content) and content[pos2].isspace():
            pos2 += 1
        if pos2 < len(content) and content[pos2] == '{':
            meaning = extract_balanced(content, pos2)
            if symbol.strip() and meaning.strip():
                results.append({'symbol': symbol.strip(),
                                'meaning': meaning.strip(),
                                'source': 'nomenclature'})
    return results


def _extract_tabular_notations(content):
    """
    Extract 2-column symbol/description rows from tabular environments that
    look like notation tables (header matches keywords, or >=50% math rows).
    """
    NOTATION_HDR = re.compile(
        r'symbol|notation|nomenclature|variable|parameter|description|meaning',
        re.IGNORECASE
    )
    env_pat = re.compile(
        r'\\begin\{(tabular[x*]?|longtable)\}(.*?)\\end\{\1\}',
        re.DOTALL
    )
    results = []
    for env_m in env_pat.finditer(content):
        body = env_m.group(2)
        rows = []
        for row in re.split(r'\\\\', body):
            row = row.strip()
            if not row or re.match(r'^\s*\\(?:hline|toprule|midrule|bottomrule|cline)', row):
                continue
            cols = [c.strip() for c in row.split('&')]
            if len(cols) >= 2:
                rows.append(cols)

        if not rows:
            continue

        header_text = ' '.join(rows[0])
        is_notation = bool(NOTATION_HDR.search(header_text))
        if not is_notation:
            math_count = sum(1 for r in rows if r[0].startswith('$') or '\\' in r[0])
            is_notation = math_count >= len(rows) * 0.5
        if not is_notation:
            continue

        data_rows = rows[1:] if rows and not rows[0][0].startswith('$') else rows
        for cols in data_rows:
            sym  = strip_latex_formatting(cols[0])
            desc = strip_latex_formatting(cols[1]) if len(cols) > 1 else ''
            if sym and desc and len(sym) < 60:
                results.append({'symbol': sym, 'meaning': desc, 'source': 'tabular'})
    return results


def _extract_newcommands(content):
    """
    Parse \\newcommand{\\macro}{definition} as last-resort notation hints.
    Skips purely formatting macros.
    """
    results = []
    cmd_pat = re.compile(
        r'\\(?:newcommand|renewcommand|providecommand)\s*\{\\([^}]+)\}'
        r'\s*(?:\[\d+\])?\s*(?=\{)'
    )
    for m in cmd_pat.finditer(content):
        macro = '\\' + m.group(1).strip()
        defn  = extract_balanced(content, m.end()).strip()
        if re.search(r'[a-zA-Z0-9]', defn) and '\\begin' not in defn and len(defn) < 80:
            results.append({'symbol': macro, 'meaning': defn, 'source': 'newcommand'})
    return results


def extract_tex_notations(tex_path):
    """
    Entry point: extract notations from a .tex file.
    Priority: \\nomenclature > tabular tables > \\newcommand.

    Returns a list of notation dicts compatible with the PDF extraction output:
        {"symbol": str, "meaning": str, "anchors": [...]}
    """
    content = read_tex(tex_path)
    base_dir = os.path.dirname(os.path.abspath(tex_path))
    content  = resolve_inputs(content, base_dir)

    raw = []
    nom = _extract_nomenclature(content)
    if nom:
        print(f"  [.tex] Found {len(nom)} entries via \\nomenclature")
        raw.extend(nom)
    tab = _extract_tabular_notations(content)
    if tab:
        print(f"  [.tex] Found {len(tab)} entries via tabular environments")
        raw.extend(tab)
    if not raw:
        cmd = _extract_newcommands(content)
        if cmd:
            print(f"  [.tex] Found {len(cmd)} entries via \\newcommand (fallback)")
            raw.extend(cmd)

    seen, notations = set(), []
    for item in raw:
        sym = item['symbol']
        if sym not in seen:
            seen.add(sym)
            notations.append({
                'symbol':  sym,
                'meaning': item['meaning'],
                'anchors': [{
                    'section':     'LaTeX Source',
                    'subsection':  item.get('source', ''),
                    'page':        0,
                    'anchor_text': f"{sym}: {item['meaning']}"
                }]
            })
    return notations


# ---------------------------------------------------------------------------
# Equation extraction
# ---------------------------------------------------------------------------

_EQ_ENVS = [
    'equation', 'align', 'eqnarray', 'multline', 'gather',
    'equation*', 'align*', 'eqnarray*', 'multline*', 'gather*',
]


def extract_tex_equations(tex_path):
    """
    Extract labelled/numbered equations from a .tex file.

    Returns a list of candidate dicts compatible with format_equations_via_ai():
        {"label": str, "latex": str, "raw_text": str,
         "section": str, "page": 0, "context": str}
    """
    content = read_tex(tex_path)
    base_dir = os.path.dirname(os.path.abspath(tex_path))
    content  = resolve_inputs(content, base_dir)

    section_map = build_section_map(content)
    equations, eq_counter = [], 0

    for env in _EQ_ENVS:
        pat = re.compile(
            r'\\begin\{' + re.escape(env) + r'\}(.*?)\\end\{' + re.escape(env) + r'\}',
            re.DOTALL
        )
        for m in pat.finditer(content):
            body = m.group(1)
            label_m = re.search(r'\\label\{([^}]+)\}', body)
            eq_counter += 1
            label = f"Equation ({label_m.group(1).strip()})" if label_m else f"Equation ({eq_counter})"
            latex = re.sub(r'\\label\{[^}]+\}', '', body).strip()
            ctx_start = max(0, m.start() - 400)
            context = strip_latex_commands(content[ctx_start:m.start()]).strip()
            if len(context) > 300:
                context = context[-300:]
            equations.append({
                'label':    label,
                'latex':    f'$${latex}$$',
                'raw_text': latex,
                'section':  get_section_at(section_map, m.start()),
                'page':     0,
                'context':  context,
            })

    return equations


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------

def extract_tex_references(tex_path):
    """
    Extract bibliography entries from \\bibitem{key} commands in a .tex file.
    Returns a list of dicts: {"key": str, "text": str}.
    """
    content = read_tex(tex_path)
    base_dir = os.path.dirname(os.path.abspath(tex_path))
    content  = resolve_inputs(content, base_dir)

    refs, pat = [], re.compile(
        r'\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*?)'
        r'(?=\\bibitem|\\end\{thebibliography\}|$)',
        re.DOTALL
    )
    for m in pat.finditer(content):
        key  = m.group(1).strip()
        text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', m.group(2))
        text = re.sub(r'[{}\\]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if key and text:
            refs.append({'key': key, 'text': text})
    return refs


def extract_tex_cite_contexts(tex_path):
    """
    Scan the body of a .tex file for \\cite{key} usages.

    Returns a citation-context map compatible with query_gemini_to_synthesize_references():
        { "key": [{"page": 0, "section": str, "sentence": str, "full_context": str}] }
    """
    content = read_tex(tex_path)
    base_dir = os.path.dirname(os.path.abspath(tex_path))
    content  = resolve_inputs(content, base_dir)

    bib_m = re.search(r'\\begin\{thebibliography\}', content)
    body  = content[:bib_m.start()] if bib_m else content

    section_map = build_section_map(body)
    plain       = strip_latex_commands(body)
    raw_sents   = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', plain)

    cite_pat = re.compile(r'\\cite(?:p|t|alt|author)?\{([^}]+)\}')
    contexts: dict = {}

    for idx, sent in enumerate(raw_sents):
        before = raw_sents[idx - 1] if idx > 0 else ''
        after  = raw_sents[idx + 1] if idx < len(raw_sents) - 1 else ''
        full   = ' '.join(filter(None, [before, sent, after])).strip()
        for m in cite_pat.finditer(sent):
            for key in m.group(1).split(','):
                key = key.strip()
                if key:
                    contexts.setdefault(key, []).append({
                        'page':         0,
                        'section':      'LaTeX Source',
                        'sentence':     sent.strip(),
                        'full_context': full,
                    })
    return contexts
