"""ftlab: LoRA fine-tune vs retrieval few-shot vs zero-shot, measured on CPU."""

import hashlib
from pathlib import Path

from ftlab.producers import (
    PRODUCER_EXCLUDE,
    ProducerManifestError,
    derive_producer_files,
    read_producer_manifest,
    write_producer_manifest,
)

SCHEMA_VERSION = "1"
__version__ = "0.1.0"
__all__ = ["PRODUCER_EXCLUDE", "PRODUCER_FILES", "ProducerManifestError", "derive_producer_files", "read_producer_manifest", "write_producer_manifest"]
# The list that train receipts were stamped with before the list was derived; receipts without a `producer_files` manifest are checked against it.
LEGACY_PRODUCER_FILES = ("cli.py", "data.py", "engine.py", "modeling.py", "prompts.py", "splits.py")


PRODUCER_FILES = read_producer_manifest()


_MANIFEST_EDITS = (
    (b"from ftlab import PRODUCER_FILES, SCHEMA_VERSION, code_sha", b"from ftlab import SCHEMA_VERSION, code_sha"),
    (b'"code_sha": code_sha(), "producer_files": list(PRODUCER_FILES), **info', b'"code_sha": code_sha(), **info'),
)


def legacy_code_sha(pkg: Path | None = None) -> str:
    """The sha that receipts without a manifest carry: the legacy list, with cli.py read as it was before it started writing the manifest (the only edit that is undone). Retire this after the next retrain."""
    base = pkg or Path(__file__).parent
    h = hashlib.sha256()
    for name in LEGACY_PRODUCER_FILES:
        data = (base / name).read_bytes()
        if name == "cli.py":
            for new, old in _MANIFEST_EDITS:
                data = data.replace(new, old)
        h.update(name.encode() + b"\0" + data + b"\0")
    return h.hexdigest()


def code_sha(files: tuple[str, ...] | None = None, pkg: Path | None = None) -> str:
    """sha256 over the source of the files that produce train receipts; a receipt carrying another value is stale."""
    base = pkg or Path(__file__).parent
    h = hashlib.sha256()
    for name in files if files is not None else PRODUCER_FILES:
        h.update(name.encode() + b"\0" + (base / name).read_bytes() + b"\0")
    return h.hexdigest()
