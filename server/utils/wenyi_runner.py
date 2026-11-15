"""Run the installed CLI with one invocation's explicit HTTP bridge connection.

This module executes only in the selected Wenyi Python, not in the Flask Server.
It does not import BabelDOC, mutate saved state or change the standalone CLI.
"""

import os
import sys
from contextlib import ExitStack
from urllib.parse import urlsplit

# A non-HTTP identity fails closed if used without the host's resolver. It must
# never silently go to a DNS server, proxy, default port or unrelated bridge.
LOGICAL_BRIDGE_URL = "zotero-wenyi://bridge"
BRIDGE_ENV = "ZOTERO_WENYI_BRIDGE_URL"


def main() -> None:
    url = os.environ.get(BRIDGE_ENV, "").rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("The plugin launcher requires a valid current HTTP(S) bridge URL")
    try:
        from wenyi_core.pdf_bridge.connection import (
            BridgeConnection,
            resolve_connection,
            use_bridge_connection,
        )
        from wenyi_cli.main import main as cli_main
    except ImportError as error:
        raise SystemExit(
            "This Wenyi Python lacks CLI/runtime bridge connection support. Update wenyi-cli "
            "and wenyi-core in the dedicated environment, or select their Python with "
            f"--wenyi-python. Interpreter: {sys.executable}. Missing: {error.name}"
        ) from None

    # This invocation owns exactly one bridge. Resolve saved addresses as well as
    # new extraction requests to it, without changing session IDs or PDF mappings.
    with ExitStack() as stack:
        try:
            connection = BridgeConnection(url, trust_env=False)
            stack.enter_context(use_bridge_connection(lambda _: connection))
            if resolve_connection(LOGICAL_BRIDGE_URL) != connection:
                raise TypeError("Connection resolver did not activate")
        except (TypeError, AttributeError) as error:
            raise SystemExit(
                "Incompatible Wenyi runtime bridge API; update wenyi-cli and wenyi-core "
                f"or select --wenyi-python. Interpreter: {sys.executable}. {error}"
            ) from None
        cli_main()


if __name__ == "__main__":
    main()
