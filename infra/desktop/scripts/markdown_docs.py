"""Keep generated Chinese prose consistent with the project documentation style."""
import re


def format_prose(text):
    """Remove paragraph-final Chinese full stops, preserving tables and code."""
    lines = text.splitlines(keepends=True)
    fence = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            token = marker.group()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence or stripped.startswith(("|", "#", "<!--")) or re.match(r"\[[^]]+\]:", stripped):
            continue
        if line.startswith(("    ", "\t")):
            continue
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if not following or following.startswith(("#", "|", "<!--", "```", "~~~")):
            lines[index] = re.sub(r"。[ \t]*(\r?\n)?$", lambda m: m.group(1) or "", line)
    return "".join(lines)
