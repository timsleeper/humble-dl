import os

# Rich sizes CLI help and error output to the terminal width. In a non-TTY CI
# shell that width falls back to a value narrow enough to wrap or truncate the
# strings these tests assert on (e.g. "--library-path" vanishes from help,
# "cannot both be set" gets a newline inserted). humble_dl.cli builds a
# module-level rich Console at import time, so the width must be pinned before
# that import happens -- hence here, at conftest import, rather than in a
# per-test fixture. Keeps CLI output deterministic regardless of the runner.
os.environ["COLUMNS"] = "200"
