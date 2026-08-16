FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 用鎖定版本清單建置：requirements.txt 現為 `-e .`，而專案原始碼此時尚未 COPY 進來
COPY requirements-lock.txt /tmp/requirements-lock.txt

RUN pip install --no-cache-dir --upgrade pip

RUN python - <<'PY'
from pathlib import Path

src = Path("/tmp/requirements-lock.txt")
dst = Path("/tmp/requirements.docker.txt")

out_lines = []
for raw in src.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue

    # Conda-export style: package @ file:///...
    # Keep package name so Docker can install from PyPI.
    if " @ file://" in line:
        pkg = line.split(" @ file://", 1)[0].strip()
        if pkg:
            out_lines.append(pkg)
        continue

    out_lines.append(line)

dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
PY

RUN pip install --no-cache-dir -r /tmp/requirements.docker.txt

# NOTE:
# Build this Dockerfile with project root as context:
# docker build -f core/Dockerfile -t alphaedge-core .
COPY run.py /app/run.py
COPY core /app/core

ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
