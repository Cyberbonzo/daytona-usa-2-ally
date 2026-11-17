"""Read or change the single-cabinet difficulty while the game is closed."""
import argparse
import binascii
import os
from pathlib import Path

LEVELS = ("Easy", "Normal", "Hard", "Hardest")
ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "state/save/backup.bin"

def read_image(blob):
    if len(blob) != 131200:
        raise ValueError("Unexpected cabinet backup size")
    raw = blob[-128:]
    image = bytearray(raw[i ^ 1] for i in range(128))
    payload = image[12:70]
    if (image[:6] != b"M3SEGA" or payload != image[70:128]
            or binascii.crc_hqx(payload, 0) != int.from_bytes(image[6:8], "big")
            or image[33] >= len(LEVELS)):
        raise ValueError("Invalid cabinet EEPROM")
    return image

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=LEVELS, nargs="?")
    args = parser.parse_args()
    blob = BACKUP.read_bytes()
    image = read_image(blob)
    if args.level is None or args.level == LEVELS[image[33]]:
        print(LEVELS[image[33]])
        return
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            if (entry/"cwd").resolve(strict=True) == ROOT and b"src/play.py" in (entry/"cmdline").read_bytes().split(b"\0"):
                raise SystemExit("Close Daytona USA 2 before changing its cabinet.")
        except (OSError, RuntimeError):
            continue
    image[33] = LEVELS.index(args.level)
    image[12:14] = ((int.from_bytes(image[12:14], "big")+1) & 65535).to_bytes(2,"big")
    image[6:8] = binascii.crc_hqx(image[12:70],0).to_bytes(2,"big")
    image[70:] = image[12:70]
    result = blob[:-128] + bytes(image[i ^ 1] for i in range(128))
    assert read_image(result)[33] == LEVELS.index(args.level)
    import tempfile
    with tempfile.NamedTemporaryFile(dir=BACKUP.parent,delete=False) as out:
        tmp = Path(out.name)
        try:
            out.write(result); out.flush(); os.fsync(out.fileno())
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
    try:
        if BACKUP.read_bytes() != blob:
            raise RuntimeError("Cabinet changed during update")
        os.replace(tmp,BACKUP)
    finally:
        tmp.unlink(missing_ok=True)
    print(LEVELS[read_image(BACKUP.read_bytes())[33]])

if __name__ == "__main__":
    main()
