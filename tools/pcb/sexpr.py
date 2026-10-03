"""Minimal KiCad S-expression reader and writer.

Parses the .kicad_sch, .kicad_pcb, .kicad_mod and netlist formats into
nested Python lists. Atoms are str; quoted strings are kept as Str so the
writer can re-quote them.
"""


class Str(str):
    """A quoted string token (written back with double quotes)."""


def parse(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(Str("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n()":
                j += 1
            tokens.append(text[i:j])
            i = j
    stack = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return stack[0][0] if stack[0] else None


def quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dumps(node, indent=0):
    """Serialize a node tree in KiCad's style (one child list per line)."""
    pad = "\t" * indent
    if not isinstance(node, list):
        return quote(node) if isinstance(node, Str) else str(node)
    if not node:
        return "()"
    head = node[0]
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return "(" + " ".join(dumps(x) for x in node) + ")"
    parts = []
    inline = []
    for x in node:
        if isinstance(x, list):
            parts.append(dumps(x, indent + 1))
        else:
            inline.append(dumps(x))
    head_s = " ".join(inline)
    body = "".join("\n" + "\t" * (indent + 1) + p for p in parts)
    return "(" + head_s + body + "\n" + pad + ")"


def find_all(node, name):
    """Yield direct children of node whose head is name."""
    if not isinstance(node, list):
        return
    for x in node:
        if isinstance(x, list) and x and x[0] == name:
            yield x


def find_one(node, name):
    return next(find_all(node, name), None)
