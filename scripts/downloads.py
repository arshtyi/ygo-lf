from __future__ import annotations

import shutil
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path


Validator = Callable[[Path], bool]


def download_file(
    url: str,
    destination: Path,
    *,
    timeout: float = 120.0,
    validator: Validator | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, 4):
        temporary: Path | None = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ygo-lf-builder"})
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as output:
                temporary = Path(output.name)
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    shutil.copyfileobj(response, output)
            if validator is not None and not validator(temporary):
                raise ValueError(f"downloaded file failed validation: {url}")
            temporary.replace(destination)
            return
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = error
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(attempt)

    raise RuntimeError(f"failed to download {url}: {last_error}")
