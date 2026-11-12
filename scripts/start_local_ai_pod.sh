#!/bin/bash
# ==============================================================================
# OpenSciencePipe: Local AI Pod Launcher (Podman)
# Runs 100% offline, zero-cloud API bibliometric & systematic review pipeline.
#
# Services inside pod 'openscience-ai-pod':
#   1. Ollama (Local open-weight LLMs for thematic buckets & zero-shot triage)
#   2. OpenSciencePipe (cuGraph network analysis & BERTopic neural topic modeling)
# ==============================================================================

set -e

POD_NAME="openscience-ai-pod"
OLLAMA_CONTAINER="osp-ollama"
MODEL_NAME="${1:-llama3.2:3b}"

ACTION="${1:-start}"

if [ "$ACTION" == "stop" ]; then
    echo "Stopping and removing local AI pod '${POD_NAME}'..."
    podman pod stop "$POD_NAME" 2>/dev/null || true
    podman pod rm -f "$POD_NAME" 2>/dev/null || true
    echo "Local AI pod stopped."
    exit 0
fi

# Detect NVIDIA GPU CDI or device flag
GPU_FLAGS="--device nvidia.com/gpu=all"
if ! podman run --rm $GPU_FLAGS docker.io/library/alpine true 2>/dev/null; then
    # Fallback to direct nvidia device nodes if CDI is not set up
    if [ -e /dev/nvidiactl ]; then
        GPU_FLAGS="--device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm"
    else
        GPU_FLAGS=""
        echo "[WARNING] No NVIDIA GPU detected. Running in CPU mode."
    fi
fi

# 1. Create shared network pod if it doesn't already exist
if ! podman pod exists "$POD_NAME" 2>/dev/null; then
    echo "Creating Podman pod '${POD_NAME}' (Ports: 8000, 11434)..."
    podman pod create --name "$POD_NAME" -p 8000:8000 -p 11434:11434
else
    echo "Pod '${POD_NAME}' already exists."
fi

# 2. Launch Ollama in the pod
if ! podman container exists "$OLLAMA_CONTAINER" 2>/dev/null; then
    echo "Launching Ollama container inside '${POD_NAME}'..."
    podman run -d \
        --pod "$POD_NAME" \
        $GPU_FLAGS \
        -v ollama_models:/root/.ollama \
        --name "$OLLAMA_CONTAINER" \
        docker.io/ollama/ollama:latest
else
    # Ensure it is running
    podman start "$OLLAMA_CONTAINER" 2>/dev/null || true
fi

echo "Waiting for Ollama to become healthy at http://localhost:11434..."
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do
    sleep 1
done

# 3. Pull required model if not present
echo "Checking model '${MODEL_NAME}' in Ollama..."
if ! podman exec "$OLLAMA_CONTAINER" ollama list | grep -q "$MODEL_NAME"; then
    echo "Pulling '${MODEL_NAME}' into local Ollama storage..."
    podman exec -it "$OLLAMA_CONTAINER" ollama pull "$MODEL_NAME"
fi

echo "================================================================================"
echo " SUCCESS: Local AI Pod '${POD_NAME}' is ready!"
echo "   - Ollama API:        http://localhost:11434 (Model: ${MODEL_NAME})"
echo "   - Web Dashboard API: http://localhost:8000"
echo "================================================================================"
echo ""
echo " Run an end-to-end analysis with Local AIs only (BERTopic + LLM Buckets):"
echo ""
echo "   podman run --pod ${POD_NAME} $GPU_FLAGS --rm -it \\"
echo "     -v \$(pwd):/app:z opensciencepipe \\"
echo "     biblio-pipeline --query \"brain-computer interface\" \\"
echo "                     --mode systematic \\"
echo "                     --screen-llm \\"
echo "                     --llm-model ${MODEL_NAME}"
echo ""
echo " To stop the local AI pod when finished:"
echo "   ./scripts/start_local_ai_pod.sh stop"
echo "================================================================================"
