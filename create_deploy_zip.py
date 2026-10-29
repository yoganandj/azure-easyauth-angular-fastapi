"""Creates a production-ready deploy.zip for Azure App Service Deployment Center."""

import os
from pathlib import Path
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = WORKSPACE_ROOT / "backend"
ZIP_OUTPUT = WORKSPACE_ROOT / "deploy.zip"

INCLUDE_ROOT_FILES = [
    "main.py",
    "requirements.txt",
    "startup.sh",
    ".deployment",
]

INCLUDE_DIRS = [
    "app",
    "static",
]

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
}

EXCLUDE_PATTERNS = [
    "__pycache__",
    ".venv",
    ":Zone.Identifier",
    "test_",
]


def should_exclude(file_path: Path) -> bool:
    str_path = str(file_path)
    if any(pat in str_path for pat in EXCLUDE_PATTERNS):
        return True
    if file_path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    return False


def create_zip():
    print(f"Creating Azure App Service deployment package at: {ZIP_OUTPUT}")
    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()

    with zipfile.ZipFile(ZIP_OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Add root config files
        for fname in INCLUDE_ROOT_FILES:
            src = BACKEND_DIR / fname
            if src.exists():
                zinfo = zipfile.ZipInfo.from_file(src, arcname=fname)
                if fname.endswith(".sh"):
                    # Set executable permissions (rwxr-xr-x -> 0o755)
                    zinfo.external_attr = 0o100755 << 16
                zf.writestr(zinfo, src.read_bytes())
                print(f"  + Added: {fname}")
            else:
                print(f"  ! Warning: {fname} not found in {BACKEND_DIR}")

        # 2. Add directories
        for dname in INCLUDE_DIRS:
            dir_path = BACKEND_DIR / dname
            if not dir_path.exists():
                print(f"  ! Warning: Directory {dname} does not exist!")
                continue

            for root, dirs, files in os.walk(dir_path):
                # Filter dirs in place
                dirs[:] = [d for d in dirs if not any(pat in d for pat in EXCLUDE_PATTERNS)]

                for f in files:
                    file_path = Path(root) / f
                    if should_exclude(file_path):
                        continue

                    rel_path = file_path.relative_to(BACKEND_DIR)
                    zinfo = zipfile.ZipInfo.from_file(file_path, arcname=str(rel_path))
                    zf.writestr(zinfo, file_path.read_bytes())
                    print(f"  + Added: {rel_path}")

    size_kb = ZIP_OUTPUT.stat().st_size / 1024
    print(f"\nSuccessfully generated {ZIP_OUTPUT.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    create_zip()
