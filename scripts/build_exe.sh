#!/usr/bin/env bash
set -euo pipefail

# Build a PyInstaller onedir executable of gearrec.
# Outputs to dist/gearrec-<os>-<arch>/gearrec[.exe]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-build"

python -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip
pip install -e "${ROOT_DIR}[dev]"

pytest

pyinstaller "${ROOT_DIR}/packaging/pyinstaller/gearrec.spec"

OS_NAME=$(python - <<'PY'
import platform
print(platform.system().lower())
PY
)
ARCH=$(python - <<'PY'
import platform
print(platform.machine().lower())
PY
)
SRC_DIR="${ROOT_DIR}/dist/gearrec"
TARGET_DIR="${ROOT_DIR}/dist/gearrec-${OS_NAME}-${ARCH}"
rm -rf "${TARGET_DIR}"
if [ -d "${SRC_DIR}" ]; then
  mv "${SRC_DIR}" "${TARGET_DIR}"
fi
if [ -f "${ROOT_DIR}/dist/gearrec.exe" ]; then
  if [ -f "${TARGET_DIR}/gearrec.exe" ]; then
    rm "${ROOT_DIR}/dist/gearrec.exe"
  else
    mv "${ROOT_DIR}/dist/gearrec.exe" "${TARGET_DIR}/gearrec.exe"
  fi
fi

echo "Build complete. See dist/ for output:"
ls -la "${ROOT_DIR}/dist"
