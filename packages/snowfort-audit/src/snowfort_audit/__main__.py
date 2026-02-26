"""Entry point: wires the container then runs the CLI. Enables Interface to avoid importing Infrastructure."""

# Suppress third-party dependency version warnings before any import that loads snowflake/requests.
import warnings

warnings.filterwarnings("ignore", message=r".*urllib3.*chardet.*doesn't match a supported version.*")
warnings.filterwarnings("ignore", module="requests")
warnings.filterwarnings("ignore", module="snowflake.connector.vendored.requests")

from snowfort_audit.di.container import AuditContainer  # noqa: E402
from snowfort_audit.infrastructure.wiring import register_all  # noqa: E402
from snowfort_audit.interface.cli import main as cli_main  # noqa: E402


def main():
    container = AuditContainer()
    register_all(container)
    cli_main(prog_name="snowfort", obj=container)


if __name__ == "__main__":
    main()
