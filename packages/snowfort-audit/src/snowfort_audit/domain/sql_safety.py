"""SQL identifier and literal escaping helpers.

Used wherever a value fetched from ACCOUNT_USAGE / SHOW commands is interpolated
back into a follow-up SQL statement. Even though those values come from Snowflake's
own catalog, a customer object can be created with arbitrary characters inside a
quoted identifier (Snowflake permits ``"foo'); DROP TABLE x; --"`` as a name when
QUOTED_IDENTIFIERS_IGNORE_CASE is on). Treating those values as untrusted prevents
an attacker who can ``CREATE`` an object with an injecting name from running
arbitrary SQL when an audit runs as a privileged role.
"""

from __future__ import annotations

import re

# Identifier shape per Snowflake docs: letter or underscore start, alphanumeric or
# underscore body; ``$`` permitted in body. Anything outside this shape must be
# rejected or routed through a fully-quoted-identifier escape.
_UNQUOTED_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def is_safe_unquoted_identifier(name: str) -> bool:
    """Return True iff ``name`` matches the unquoted-identifier grammar exactly."""
    return bool(_UNQUOTED_IDENT_RE.fullmatch(name or ""))


def quote_identifier(name: str) -> str:
    """Return a Snowflake-quoted identifier safe to interpolate into SQL.

    Doubles any embedded double-quote character per the Snowflake identifier
    grammar — ``foo"bar`` becomes ``"foo""bar"``.
    """
    if name is None:
        raise ValueError("identifier may not be None")
    return '"' + str(name).replace('"', '""') + '"'


def quote_fqdn(*parts: str) -> str:
    """Quote a multi-part FQDN (e.g. ``DB.SCHEMA.TABLE``) component-by-component."""
    return ".".join(quote_identifier(p) for p in parts)


def escape_string_literal(value: str) -> str:
    """Escape ``value`` for safe interpolation inside single-quoted SQL literal.

    Doubles single quotes and backslashes per the Snowflake string-literal grammar.
    Prefer parameterised binds (``%s``) over this helper when the connector path
    supports it; reach for it only for positions binds don't reach (e.g. SHOW
    commands or function-call positional args).
    """
    return str(value).replace("\\", "\\\\").replace("'", "''")
