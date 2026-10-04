# RAPIDS 25.06 / CUDA 12.8 (host driver 615.x; RAPIDS 24.12 segfaults in
# UCX teardown against this driver — see paper-3 GPU notes)
FROM nvcr.io/nvidia/rapidsai/base:25.06-cuda12.8-py3.11

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv

WORKDIR /app

# Copy the dependency files and src first
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src

# Install project dependencies
# Torch trio from the pinned cu124 index (CUDA 12.x forward-compatible with
# the 12.8 runtime); the RAPIDS 25.06 base is what fixes the UCX teardown crash.
RUN /uvbin/uv pip install --system --no-cache \
    "torch>=2.5.1,<2.7" \
    "torchvision>=0.20.1,<0.22" \
    "torchaudio>=2.5.1,<2.8" \
    "nvidia-cuda-runtime-cu12" \
    "nvidia-cudnn-cu12" \
    "nvidia-cublas-cu12" \
    "nvidia-curand-cu12" \
    "nvidia-cusolver-cu12" \
    "nvidia-cusparse-cu12" \
    "nvidia-nccl-cu12" \
    "nvidia-nvtx-cu12" \
    "python-louvain" \
    .

LABEL maintainer="Bibliometric Research Team"
LABEL description="Containerized Bibliometric Research Pipeline with GPU support and FastAPI Backend"

# Set environment variables for the SSD and GPU
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV UV_LINK_MODE=copy

# FastAPI port
EXPOSE 8000

# The entrypoint will use the RAPIDS environment's python
ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
