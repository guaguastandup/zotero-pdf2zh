"""Plugin-owned Wenyi data, separate from installations and other Wenyi hosts."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WenyiPaths:
    data: Path
    cache: Path

    @classmethod
    def resolve(
        cls, data: str | Path | None = None, cache: str | Path | None = None
    ) -> "WenyiPaths":
        """Resolve paths without creating, discovering or migrating any data."""
        data = data or os.environ.get("ZOTERO_WENYI_DATA_DIR")
        if not data:
            home = Path.home()
            if sys.platform == "win32":
                base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
            elif sys.platform == "darwin":
                base = home / "Library" / "Application Support"
            else:
                base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share")
            data = base / "zotero-pdf2zh" / "wenyi"
        data = Path(data).expanduser().resolve()
        cache = cache or os.environ.get("ZOTERO_WENYI_CACHE_DIR") or data / "cache"
        cache = Path(cache).expanduser().resolve()
        protected = [data / name for name in ("tasks", "translations", "bridge", "runtime")]
        if (
            cache == data
            or cache in data.parents
            or any(cache == path or path in cache.parents for path in protected)
        ):
            raise ValueError(
                "Wenyi cache must not contain data or overlap tasks/state/sessions/runtime"
            )
        return cls(data, cache)

    @property
    def tasks(self) -> Path:
        return self.data / "tasks"

    @property
    def translations(self) -> Path:
        return self.data / "translations"

    @property
    def sessions(self) -> Path:
        return self.data / "bridge" / "sessions"

    @property
    def runtime(self) -> Path:
        return self.data / "runtime"
