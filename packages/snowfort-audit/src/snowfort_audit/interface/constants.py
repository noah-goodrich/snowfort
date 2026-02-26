"""
Stellar Engineering Command: Visual Telemetry Constants
"""

# SNOWARCH: ANSI Cyan (\033[36m)
_CYAN = "\033[36m"
_RESET = "\033[0m"
_SNOWARCH_ART = r"""
   _____ _   ______ _       _____    ____  ________  __
  / ___// | / / __ \ |     / /   |  / __ \/ ____/ / / /
  \__ \/  |/ / / / / | /| / / /| | / /_/ / /   / /_/ /
 ___/ / /|  / /_/ /| |/ |/ / ___ |/ _, _/ /___/ __  /
/____/_/ |_/\____/ |__/|__/_/  |_/_/ |_|\____/_/ /_/
"""
SNOWARCH_BANNER = _CYAN + _SNOWARCH_ART + _RESET

# Snowfort: minified header for help and compact contexts
SNOWFORT_HEADER_MINIFIED = """* snowfort
  ===========
  Well-Architected Toolkit for Snowflake"""

# Snowfort: top-level CLI help (legacy alias)
SNOWFORT_BANNER = _CYAN + "Snowfort – Snowflake architecture tools\n" + _RESET


def get_snowfort_splash() -> str:
    """Return full ASCII splash art for initial CLI display (cyan)."""
    try:
        from importlib import resources as _res

        content = _res.files("snowfort_audit").joinpath("resources", "snowfort_ascii.txt").read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError):
        content = SNOWFORT_HEADER_MINIFIED
    return _CYAN + content.strip("\n") + _RESET
