"""Launch the installed bridge on a private ephemeral port in its own Python."""

import asyncio
import json
import multiprocessing
import os
import socket
import sys
import threading
from importlib.metadata import version
from pathlib import Path


def configure_cache() -> None:
    """Configure assets before importing the pipeline, also in spawned PDF workers."""
    cache = Path(os.environ["ZOTERO_WENYI_CACHE_DIR"])
    cache.mkdir(parents=True, exist_ok=True)
    import babeldoc.const as const

    # BabelDOC 0.7.1 exposes cache paths through these constants, not an env var.
    # Unlike the Desktop offline pack, this cache may download missing resources.
    const.CACHE_FOLDER = cache
    const.TIKTOKEN_CACHE_FOLDER = cache / "tiktoken"
    const.TIKTOKEN_CACHE_FOLDER.mkdir(parents=True, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = str(const.TIKTOKEN_CACHE_FOLDER)


async def serve(protocol):
    import uvicorn
    from wenyi_babeldoc_bridge.desktop_runtime import watch_parent

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(
                "wenyi_babeldoc_bridge.server:app",
                access_log=False,
                log_config=None,
                timeout_graceful_shutdown=5,
            )
        )
        # Reuse the pinned bridge's Windows-safe owner-pipe and PDF-child cleanup.
        threading.Thread(target=watch_parent, args=(server,), daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started and not task.done():
            await asyncio.sleep(0.01)
        if server.started and not server.should_exit:
            protocol.write(
                json.dumps(
                    {
                        "protocol": 1,
                        "port": port,
                        "pid": os.getpid(),
                        "version": version("wenyi-babeldoc-bridge"),
                    }
                )
                + "\n"
            )
            protocol.flush()
        await task


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    output = sys.stdout
    sys.stdout = sys.stderr
    configure_cache()
    asyncio.run(serve(output))
elif __name__ == "__mp_main__":
    sys.stdout = sys.stderr
    configure_cache()
