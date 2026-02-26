"""Snowflake gateway using connector only (no snowflake.core) (vendored)."""

from typing import Any
from urllib.parse import urlparse

from snowflake.connector import connect

from snowfort_audit._vendor.protocols import SnowflakeCursorProtocol, SnowflakeQueryProtocol


def _normalize_account(raw: str | None) -> str | None:
    """Extract account identifier from URL or return as-is. Connector expects identifier, not full URL."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    s = raw.strip()
    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        host = (parsed.netloc or s).split("//")[-1]
        for suffix in (".privatelink.snowflakecomputing.com", ".snowflakecomputing.com"):
            if host.endswith(suffix):
                return host[: -len(suffix)]
        return host
    return s


class SnowflakeGateway(SnowflakeQueryProtocol):
    """Snowflake connection gateway using snowflake-connector-python only.
    Supports multiple connections for parallel rule execution via get_cursor_for_worker(worker_id).
    """

    def __init__(self, options: Any | None = None):
        self.options = options
        self._connection: Any = None
        self._connection_params: dict[str, Any] | None = None
        self._pool: list[Any] = []

    def _build_connection_params(self) -> dict[str, Any]:
        if not self.options:
            raise ValueError("No connection options provided to SnowflakeGateway.")
        if isinstance(self.options, dict):
            params = dict(self.options)
            if "account" in params:
                params["account"] = _normalize_account(params.get("account"))
        else:
            auth = getattr(self.options, "auth", None)
            raw_account = getattr(self.options, "account", None)
            params = {
                "account": _normalize_account(raw_account),
                "user": getattr(self.options, "user", None),
                "password": getattr(auth, "password", None) if auth else getattr(self.options, "password", None),
                "role": getattr(self.options, "role", None),
                "authenticator": getattr(self.options, "authenticator", None),
                "passcode": getattr(auth, "passcode", None) if auth else getattr(self.options, "passcode", None),
                "private_key_path": (
                    getattr(auth, "private_key_path", None) if auth else getattr(self.options, "private_key_path", None)
                ),
            }
        connection_params = {k: v for k, v in params.items() if v is not None}
        if "authenticator" not in connection_params:
            connection_params["authenticator"] = "externalbrowser"
        if "role" not in connection_params:
            connection_params["role"] = "ACCOUNTADMIN"
        return connection_params

    def connect(self) -> None:
        if self._connection:
            return
        params = self._build_connection_params()
        self._connection_params = params
        self._connection = connect(**params)

    def get_cursor(self) -> SnowflakeCursorProtocol:
        if not self._connection:
            self.connect()
        return self._connection.cursor()

    def get_cursor_for_worker(self, worker_id: int) -> SnowflakeCursorProtocol:
        """Return a cursor for this worker. Worker 0 uses the main connection (established first).
        Workers 1..N use pool connections so we only create N-1 extra connections after the first.
        Thread-safe: each thread should use its own worker_id (0..N-1).
        """
        if worker_id == 0:
            return self.get_cursor()
        if not self._connection_params:
            self.connect()
        assert self._connection_params is not None
        # Pool index 0 = worker 1, index 1 = worker 2, ...
        pool_index = worker_id - 1
        while len(self._pool) <= pool_index:
            self._pool.append(connect(**self._connection_params))
        return self._pool[pool_index].cursor()

    def execute(self, query: str, params: Any | None = None) -> Any:
        cursor = self.get_cursor()
        cursor.execute(query, params)
        return cursor

    def execute_ddl(self, builder: Any) -> Any:
        if hasattr(builder, "build"):
            return self.execute(builder.build())
        raise ValueError(f"Builder {type(builder)} does not have a build() method")

    def close(self) -> None:
        for conn in self._pool:
            try:
                conn.close()
            except Exception:
                pass
        self._pool.clear()
        if self._connection:
            self._connection.close()
            self._connection = None
