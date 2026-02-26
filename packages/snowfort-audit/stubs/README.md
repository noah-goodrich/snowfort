# Type stubs for third-party packages

Used by mypy via `mypy_path = "stubs"` in `pyproject.toml`.

- **pandas**, **plotly**, **plotly.express**, **plotly.graph_objects**: Generated with `stubgen -m <module> -o <dir>` (mypy’s stubgen), then trimmed to minimal interfaces so stubs do not pull in missing submodule stubs.
- **snowflake.snowpark**, **snowflake.snowpark.context**: Minimal hand-written stubs (snowpark is optional; stubgen cannot run without the package installed).
- **tomli**: Minimal hand-written stub for when Python < 3.11 (otherwise stdlib `tomllib` is used).

To regenerate pandas/plotly stubs:

```bash
stubgen -m pandas -o /tmp/out && cp -r /tmp/out/pandas stubs/
stubgen -m plotly -o /tmp/out && cp -r /tmp/out/plotly stubs/
stubgen -m plotly.express -o /tmp/out && cp -r /tmp/out/plotly/express stubs/plotly/
stubgen -m plotly.graph_objects -o /tmp/out && cp -r /tmp/out/plotly/graph_objects stubs/plotly/
```

Then trim the generated `.pyi` files to remove re-exports from submodules that have no stubs (or keep the minimal stubs under `stubs/pandas` and `stubs/plotly` as-is).
