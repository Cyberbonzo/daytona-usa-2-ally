"""Atomic persistence for the arcade board's SRAM and EEPROM."""
import os
import tempfile
from pathlib import Path
from difficulty import read_image

def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.cabinet-', delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)

def load(path):
    """Recover an interrupted or truncated primary from the previous valid image."""
    previous = path.with_suffix('.previous.bin')
    for candidate in (path, previous):
        try:
            blob = candidate.read_bytes()
            read_image(blob)
        except (FileNotFoundError, ValueError):
            continue
        if candidate != path:
            atomic_write(path, blob)
            print('Recovered previous cabinet save', flush=True)
        return blob
    if path.exists() or previous.exists():
        raise ValueError("No valid cabinet save found; both copies have been retained.")
    return None

def commit(path, data):
    read_image(data)
    prior = load(path)
    previous = path.with_suffix('.previous.bin')
    if prior is not None and (prior != data or not previous.exists()):
        atomic_write(previous, prior)
    if data != prior:
        atomic_write(path, data)
