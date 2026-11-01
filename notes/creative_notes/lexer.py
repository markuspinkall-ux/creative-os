"""Syntaxfarben: Sprachen und ein kleiner Zeilen-Lexer (ohne Qt, daher testbar).

highlight_line(lang, text, state) → (spans, neuer_state)
  spans: Liste von (start, länge, art) – art z. B. "keyword", "string", "comment"
  state: 0 = normal, 1 = in Blockkommentar, 2/3 = in ''' / \"\"\" (Python), 4 = in `…` (JS)
"""

import re

NUMBER = r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?)[a-zA-Z]*\b"

C_LIKE_TYPES = "bool char double float int long short signed unsigned void auto size_t uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t string String Object"


def _w(words):
    return set(words.split())


LANGUAGES = {
    "text": {"name": "Normaler Text", "ext": ["txt", "log", "text"]},
    "python": {
        "name": "Python", "ext": ["py", "pyw", "pyi"], "first": r"^#!.*python",
        "keywords": _w("and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case"),
        "constants": _w("True False None self cls"),
        "types": _w("int float str bool list dict set tuple bytes object type Exception"),
        "builtins": _w("print len range open isinstance enumerate zip map filter sorted sum min max abs any all super getattr setattr hasattr repr input"),
        "line": ["#"], "strings": "'\"", "triple": True, "prefix": "rbfuRBFU",
        "extra": [(r"@[\w.]+", "decorator"), (r"\bdef\s+(\w+)", "function"), (r"\bclass\s+(\w+)", "type")],
    },
    "javascript": {
        "name": "JavaScript / TypeScript", "ext": ["js", "mjs", "cjs", "jsx", "ts", "tsx"],
        "keywords": _w("async await break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield interface type enum implements private public protected readonly as"),
        "constants": _w("true false null undefined NaN Infinity"),
        "types": _w("string number boolean any unknown never object Array Promise Map Set Date"),
        "builtins": _w("console window document Math JSON require module exports"),
        "line": ["//"], "block": ("/*", "*/"), "strings": "'\"`", "template": True,
        "extra": [(r"\bfunction\s+(\w+)", "function"), (r"\b(\w+)\s*(?=\()", "call")],
    },
    "json": {
        "name": "JSON", "ext": ["json", "jsonc", "geojson", "webmanifest"],
        "constants": _w("true false null"), "line": ["//"], "block": ("/*", "*/"), "strings": "\"",
        "extra": [(r"(\"(?:[^\"\\]|\\.)*\")\s*:", "key")], "key_over_string": True,
    },
    "html": {
        "name": "HTML / XML", "ext": ["html", "htm", "xhtml", "xml", "svg", "ui", "qrc", "plist", "xsd", "xsl", "vue"],
        "block": ("<!--", "-->"), "strings": "\"'", "strings_in_tags": True,
        "extra": [(r"</?([\w:.-]+)", "tag"), (r"\s([\w:-]+)(?==)", "attribute"), (r"&\w+;|&#\d+;", "constant"),
                  (r"<\?.*?\?>|<!DOCTYPE[^>]*>", "decorator")],
    },
    "css": {
        "name": "CSS", "ext": ["css", "scss", "sass", "less", "qss"],
        "block": ("/*", "*/"), "line_in": ["scss", "less"], "strings": "\"'",
        "extra": [(r"([.#]?[\w-]+)(?=[^{};]*\{)", "tag"), (r"([\w-]+)\s*:(?!:)", "attribute"),
                  (r"#[0-9a-fA-F]{3,8}\b", "number"), (r"@[\w-]+", "keyword"), (r"!important", "keyword")],
    },
    "c": {
        "name": "C / C++", "ext": ["c", "h", "cpp", "cc", "cxx", "hpp", "hh", "hxx", "ino"],
        "keywords": _w("break case catch class const constexpr continue default delete do else enum explicit extern for friend goto if inline namespace new noexcept operator private protected public return sizeof static struct switch template this throw try typedef typename union using virtual volatile while"),
        "constants": _w("true false NULL nullptr"), "types": _w(C_LIKE_TYPES),
        "line": ["//"], "block": ("/*", "*/"), "strings": "\"'",
        "extra": [(r"^\s*#\s*\w+", "decorator"), (r"\b(\w+)\s*(?=\()", "call")],
    },
    "java": {
        "name": "Java / C# / Kotlin", "ext": ["java", "cs", "kt", "kts", "scala", "groovy", "gradle", "dart", "swift"],
        "keywords": _w("abstract break case catch class const continue default do else enum extends final finally for if implements import instanceof interface native new package private protected public return static super switch synchronized this throw throws try volatile while var val fun override namespace using async await get set let func struct in is as when object"),
        "constants": _w("true false null"), "types": _w(C_LIKE_TYPES + " Integer Boolean List Map void"),
        "line": ["//"], "block": ("/*", "*/"), "strings": "\"'",
        "extra": [(r"@\w+", "decorator"), (r"\b(\w+)\s*(?=\()", "call")],
    },
    "rust": {
        "name": "Rust", "ext": ["rs"],
        "keywords": _w("as async await break const continue crate dyn else enum extern fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait type unsafe use where while"),
        "constants": _w("true false None Some Ok Err"), "types": _w("i8 i16 i32 i64 i128 isize u8 u16 u32 u64 u128 usize f32 f64 bool char str String Vec Option Result Box"),
        "line": ["//"], "block": ("/*", "*/"), "strings": "\"",
        "extra": [(r"#!?\[[^\]]*\]", "decorator"), (r"\b\w+!", "builtin"), (r"\bfn\s+(\w+)", "function")],
    },
    "go": {
        "name": "Go", "ext": ["go"],
        "keywords": _w("break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var"),
        "constants": _w("true false nil iota"), "types": _w("int int8 int16 int32 int64 uint uint8 uint16 uint32 uint64 float32 float64 string bool byte rune error any"),
        "line": ["//"], "block": ("/*", "*/"), "strings": "\"'`",
        "extra": [(r"\bfunc\s+(?:\([^)]*\)\s*)?(\w+)", "function")],
    },
    "shell": {
        "name": "Shell / Bash", "ext": ["sh", "bash", "zsh", "ksh", "bashrc", "profile", "env"], "first": r"^#!.*\b(ba|z|k)?sh\b",
        "keywords": _w("if then else elif fi case esac for while until do done in function return break continue local export readonly declare set unset shift exit source trap"),
        "builtins": _w("echo printf cd ls cp mv rm mkdir cat grep sed awk test read eval exec sudo dnf rpm-ostree systemctl"),
        "line": ["#"], "strings": "\"'",
        "extra": [(r"\$\{[^}]*\}|\$\w+|\$[@#?$!*0-9]", "constant"), (r"^\s*([\w-]+)\s*\(\)", "function")],
    },
    "php": {
        "name": "PHP", "ext": ["php", "phtml"],
        "keywords": _w("abstract and array as break case catch class clone const continue declare default do echo else elseif empty enddeclare endfor endforeach endif endswitch endwhile extends final finally fn for foreach function global if implements include include_once instanceof interface isset list match namespace new or print private protected public require require_once return static switch throw trait try unset use var while yield"),
        "constants": _w("true false null TRUE FALSE NULL"),
        "line": ["//", "#"], "block": ("/*", "*/"), "strings": "\"'",
        "extra": [(r"\$\w+", "constant"), (r"<\?php|\?>", "decorator")],
    },
    "sql": {
        "name": "SQL", "ext": ["sql"], "ci": True,
        "keywords": _w("select from where and or not insert into values update set delete create table drop alter add index primary key foreign references join left right inner outer on group by order having limit offset as distinct union all exists in is null like between case when then else end begin commit rollback view trigger default unique"),
        "types": _w("int integer bigint smallint varchar char text date datetime timestamp boolean float double decimal blob"),
        "line": ["--"], "block": ("/*", "*/"), "strings": "'\"",
    },
    "lua": {
        "name": "Lua", "ext": ["lua"],
        "keywords": _w("and break do else elseif end for function goto if in local not or repeat return then until while"),
        "constants": _w("true false nil"), "line": ["--"], "strings": "\"'",
    },
    "ini": {
        "name": "INI / Konfiguration", "ext": ["ini", "conf", "cfg", "desktop", "service", "timer", "socket", "toml", "properties", "editorconfig", "gitconfig", "kdeglobals", "colors", "theme", "rules"],
        "line": [";", "#"], "line_at_start": True, "strings": "\"",
        "extra": [(r"^\s*(\[[^\]]*\])", "tag"), (r"^\s*([^=;#\[\s][^=]*?)\s*(?==)", "attribute"),
                  (r"\b(true|false|yes|no|on|off)\b", "constant")],
    },
    "yaml": {
        "name": "YAML", "ext": ["yml", "yaml"],
        "line": ["#"], "strings": "\"'",
        "extra": [(r"^\s*-?\s*([\w.\-/ ]+?)\s*:(?=\s|$)", "attribute"), (r"\b(true|false|null|yes|no)\b", "constant"),
                  (r"^---$|^\.\.\.$", "decorator"), (r"&\w+|\*\w+", "constant")],
    },
    "markdown": {
        "name": "Markdown", "ext": ["md", "markdown", "mdown"],
        "extra": [(r"^#{1,6}\s.*$", "heading"), (r"\*\*[^*]+\*\*|__[^_]+__", "bold"), (r"(?<![*\w])\*[^*\s][^*]*\*(?!\*)", "italic"),
                  (r"`[^`]+`", "string"), (r"\[[^\]]*\]\([^)]*\)", "link"), (r"^\s*(?:[-*+]|\d+\.)\s", "keyword"),
                  (r"^\s*>.*$", "comment"), (r"^```.*$", "decorator")],
    },
    "makefile": {
        "name": "Makefile / Dockerfile", "ext": ["mk", "mak", "makefile", "containerfile", "dockerfile"],
        "keywords": _w("FROM RUN COPY ADD ENV ARG WORKDIR CMD ENTRYPOINT EXPOSE LABEL USER VOLUME include ifeq ifneq else endif define endef export"),
        "line": ["#"], "strings": "\"'",
        "extra": [(r"\$\([^)]*\)|\$\{[^}]*\}|\$\w+", "constant"), (r"^([\w.\-/ ]+):(?!=)", "function")],
    },
}

FILENAMES = {"makefile": "makefile", "gnumakefile": "makefile", "dockerfile": "makefile", "containerfile": "makefile",
             ".bashrc": "shell", ".bash_profile": "shell", ".profile": "shell", ".zshrc": "shell",
             "cmakelists.txt": "makefile", ".gitignore": "ini", "kwinrc": "ini", "kdeglobals": "ini"}

_EXT = {e: key for key, spec in LANGUAGES.items() for e in spec.get("ext", [])}


def detect(filename, first_line=""):
    name = (filename or "").rsplit("/", 1)[-1].lower()
    if name in FILENAMES:
        return FILENAMES[name]
    if "." in name:
        ext = name.rsplit(".", 1)[1]
        if ext in _EXT:
            return _EXT[ext]
    for key, spec in LANGUAGES.items():
        if spec.get("first") and re.match(spec["first"], first_line or ""):
            return key
    if (first_line or "").lstrip().startswith(("<?xml", "<!DOCTYPE", "<html")):
        return "html"
    return "text"


# ---- Lexer --------------------------------------------------------------------------
_compiled = {}


def _rules(lang):
    if lang in _compiled:
        return _compiled[lang]
    spec = LANGUAGES[lang]
    flags = re.IGNORECASE if spec.get("ci") else 0
    rules = []
    for kind in ("keywords", "constants", "types", "builtins"):
        words = spec.get(kind)
        if words:
            rx = re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) + r")\b", flags)
            rules.append((rx, {"keywords": "keyword", "constants": "constant", "types": "type", "builtins": "builtin"}[kind]))
    if lang not in ("text", "markdown"):
        rules.append((re.compile(NUMBER), "number"))
    for pattern, kind in spec.get("extra", []):
        rules.append((re.compile(pattern, re.MULTILINE), kind))
    _compiled[lang] = rules
    return rules


def highlight_line(lang, text, state=0):
    spec = LANGUAGES.get(lang)
    if not spec or lang == "text":
        return [], 0
    spans = []
    for rx, kind in _rules(lang):
        for m in rx.finditer(text):
            g = 1 if m.groups() and m.group(1) is not None else 0
            if m.end(g) > m.start(g):
                spans.append((m.start(g), m.end(g) - m.start(g), kind))
    if lang == "markdown":
        return spans, 0

    over = []                                   # Strings/Kommentare überdecken alles andere
    n, i = len(text), 0
    block = spec.get("block")
    lines = spec.get("line", [])
    quotes = spec.get("strings", "")
    triple = spec.get("triple")
    in_tag_only = spec.get("strings_in_tags")

    # Fortsetzung aus der vorigen Zeile
    if state == 1 and block:
        end = text.find(block[1])
        if end < 0:
            return spans + [(0, n, "comment")], 1
        over.append((0, end + len(block[1]), "comment"))
        i = end + len(block[1])
    elif state in (2, 3):
        delim = "'''" if state == 2 else '"""'
        end = text.find(delim)
        if end < 0:
            return spans + [(0, n, "string")], state
        over.append((0, end + 3, "string"))
        i = end + 3
    elif state == 4:
        end = _find_close(text, 0, "`")
        if end < 0:
            return spans + [(0, n, "string")], 4
        over.append((0, end + 1, "string"))
        i = end + 1

    new_state = 0
    tag_depth = 0
    while i < n:
        c = text[i]
        if in_tag_only:
            if c == "<":
                tag_depth = 1
            elif c == ">":
                tag_depth = 0
        if block and text.startswith(block[0], i):
            end = text.find(block[1], i + len(block[0]))
            if end < 0:
                over.append((i, n - i, "comment"))
                new_state = 1
                break
            over.append((i, end + len(block[1]) - i, "comment"))
            i = end + len(block[1])
            continue
        hit_line = False
        for lc in lines:
            if text.startswith(lc, i):
                if spec.get("line_at_start") and text[:i].strip():
                    continue
                if lc == "#" and lang == "shell" and i > 0 and text[i - 1] in "${\\":
                    continue
                hit_line = True
                break
        if hit_line:
            over.append((i, n - i, "comment"))
            break
        if triple and text.startswith(("'''", '"""'), i):
            delim = text[i:i + 3]
            end = text.find(delim, i + 3)
            if end < 0:
                over.append((i, n - i, "string"))
                new_state = 2 if delim == "'''" else 3
                break
            over.append((i, end + 3 - i, "string"))
            i = end + 3
            continue
        if c in quotes and (not in_tag_only or tag_depth):
            # In Rust/C ist ' oft ein Lebenszeit-/Zeichen-Marker – nur kurze Zeichen färben
            if c == "'" and lang == "rust":
                m = re.match(r"'(?:\\.|[^'\\])'", text[i:])
                if not m:
                    i += 1
                    continue
            end = _find_close(text, i + 1, c)
            if end < 0:
                if c == "`" and spec.get("template"):
                    over.append((i, n - i, "string"))
                    new_state = 4
                    break
                over.append((i, n - i, "string"))
                break
            over.append((i, end + 1 - i, "string"))
            i = end + 1
            continue
        i += 1

    if spec.get("key_over_string"):
        keys = [s for s in spans if s[2] == "key"]
        return [s for s in spans if s[2] != "key"] + over + keys, new_state
    return spans + over, new_state


def _find_close(text, start, quote):
    j = start
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            return j
        j += 1
    return -1


COMMENT_PREFIX = {
    "python": "# ", "shell": "# ", "yaml": "# ", "ini": "# ", "makefile": "# ", "php": "// ",
    "javascript": "// ", "json": "// ", "c": "// ", "java": "// ", "rust": "// ", "go": "// ", "css": None,
    "sql": "-- ", "lua": "-- ", "html": None, "markdown": None, "text": None,
}
BLOCK_COMMENT = {"html": ("<!-- ", " -->"), "css": ("/* ", " */"), "markdown": ("<!-- ", " -->")}
