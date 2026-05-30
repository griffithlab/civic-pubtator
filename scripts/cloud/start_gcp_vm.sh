#!/usr/bin/env bash

SRC_DIR="$(dirname "${BASH_SOURCE[0]}")"

NETWORK=civic-pubtator
SUBNET=civic-pubtator-default

# Deep Learning VM image — CUDA 12.9 + NVIDIA driver 580, Ubuntu 22.04.
# Use this family so GPU drivers are ready without a manual install step.
DEFAULT_IMAGE_FAMILY="common-cu129-ubuntu-2204-nvidia-580"
DEFAULT_IMAGE_PROJECT="deeplearning-platform-release"

# n1-standard-8: 8 vCPU / 30 GB RAM.  n1 is required for T4 attachment.
DEFAULT_MACHINE_TYPE="n1-standard-8"
DEFAULT_ACCELERATOR="nvidia-tesla-t4"
DEFAULT_ACCELERATOR_COUNT=1

# 200 GB covers OS + conda envs + repo.  Model files live on GCS and are
# synced locally via sync_tool_data.sh — keep them off the boot disk.
DEFAULT_BOOT_DISK_SIZE="500GB"

show_help () {
    cat <<EOF
$0 - Start a civic-pubtator GCP VM instance

usage: $0 INSTANCE_NAME [--argument value]*

arguments:
  -h, --help              print this block and exit
  --project               GCP project name (required)
  --machine-type          DEFAULT: ${DEFAULT_MACHINE_TYPE}
  --zone                  DEFAULT: us-central1-f
  --accelerator-type      GPU model. DEFAULT: ${DEFAULT_ACCELERATOR}
  --accelerator-count     Number of GPUs. DEFAULT: ${DEFAULT_ACCELERATOR_COUNT}
  --no-gpu                Skip GPU attachment (CPU-only instance)
  --boot-disk-size        DEFAULT: ${DEFAULT_BOOT_DISK_SIZE}
  --image-family          DEFAULT: ${DEFAULT_IMAGE_FAMILY}
  --image-project         DEFAULT: ${DEFAULT_IMAGE_PROJECT}

Additional arguments are passed directly to gcloud compute instances create.

Examples:
  # Standard GPU instance (T4)
  $0 civic-pubtator-gpu-1 --project griffith-lab

  # CPU-only instance
  $0 civic-pubtator-cpu-1 --project griffith-lab --no-gpu --machine-type e2-standard-8

  # Larger GPU (A100)
  $0 civic-pubtator-a100 --project griffith-lab \\
      --machine-type a2-highgpu-1g --accelerator-type nvidia-tesla-a100

EOF
}

die () {
    printf '%s\n\n' "$1" >&2
    show_help
    exit 1
}

INSTANCE_NAME=$1
if [ -z "$INSTANCE_NAME" ]; then
    show_help
    exit 1
fi
shift

NO_GPU=false

while test $# -gt 0; do
    case $1 in
        -h|-\?|--help)
            show_help
            exit 0
            ;;
        --project)
            [ "$2" ] || die 'ERROR: "--project" requires a non-empty argument.'
            PROJECT=$2; shift ;;
        --machine-type)
            [ "$2" ] || die 'ERROR: "--machine-type" requires a non-empty argument.'
            MACHINE_TYPE=$2; shift ;;
        --zone)
            [ "$2" ] || die 'ERROR: "--zone" requires a non-empty argument.'
            ZONE=$2; shift ;;
        --accelerator-type)
            [ "$2" ] || die 'ERROR: "--accelerator-type" requires a non-empty argument.'
            ACCELERATOR_TYPE=$2; shift ;;
        --accelerator-count)
            [ "$2" ] || die 'ERROR: "--accelerator-count" requires a non-empty argument.'
            ACCELERATOR_COUNT=$2; shift ;;
        --no-gpu)
            NO_GPU=true ;;
        --boot-disk-size)
            [ "$2" ] || die 'ERROR: "--boot-disk-size" requires a non-empty argument.'
            BOOT_DISK_SIZE=$2; shift ;;
        --image-family)
            [ "$2" ] || die 'ERROR: "--image-family" requires a non-empty argument.'
            IMAGE_FAMILY=$2; shift ;;
        --image-project)
            [ "$2" ] || die 'ERROR: "--image-project" requires a non-empty argument.'
            IMAGE_PROJECT=$2; shift ;;
        *)
            break ;;
    esac
    shift
done

[ -z "$PROJECT"       ] && die 'ERROR: "--project" is required.'
MACHINE_TYPE=${MACHINE_TYPE:-$DEFAULT_MACHINE_TYPE}
ZONE=${ZONE:-"us-central1-f"}
ACCELERATOR_TYPE=${ACCELERATOR_TYPE:-$DEFAULT_ACCELERATOR}
ACCELERATOR_COUNT=${ACCELERATOR_COUNT:-$DEFAULT_ACCELERATOR_COUNT}
BOOT_DISK_SIZE=${BOOT_DISK_SIZE:-$DEFAULT_BOOT_DISK_SIZE}
IMAGE_FAMILY=${IMAGE_FAMILY:-$DEFAULT_IMAGE_FAMILY}
IMAGE_PROJECT=${IMAGE_PROJECT:-$DEFAULT_IMAGE_PROJECT}

# GPU instances must use TERMINATE maintenance policy (no live migration).
# CPU-only instances can use MIGRATE.
if [ "$NO_GPU" = true ]; then
    MAINTENANCE_POLICY="MIGRATE"
    ACCELERATOR_FLAGS=""
    echo "Note: creating CPU-only instance (--no-gpu)"
else
    MAINTENANCE_POLICY="TERMINATE"
    ACCELERATOR_FLAGS="--accelerator type=${ACCELERATOR_TYPE},count=${ACCELERATOR_COUNT} --restart-on-failure"
    echo "Note: attaching ${ACCELERATOR_COUNT}x ${ACCELERATOR_TYPE}"
fi

gcloud compute instances create "$INSTANCE_NAME" \
    --project="$PROJECT" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --boot-disk-size="$BOOT_DISK_SIZE" \
    --boot-disk-type=pd-ssd \
    --maintenance-policy="$MAINTENANCE_POLICY" \
    --scopes=cloud-platform \
    --network="$NETWORK" \
    --subnet="$SUBNET" \
    $ACCELERATOR_FLAGS \
    --metadata-from-file=startup-script="$SRC_DIR/gcp_server_startup.py" \
    "$@"

cat <<EOF

Instance created: ${INSTANCE_NAME}

SSH into it:
    gcloud compute ssh ${INSTANCE_NAME} --zone ${ZONE} --project ${PROJECT}

Watch startup progress (from inside the VM):
    sudo journalctl -u google-startup-scripts -f

Once setup is complete, sync tool data from GCS:
    bash /opt/civic-pubtator/scripts/cloud/sync_tool_data.sh down

Delete the instance when done:
    gcloud compute instances delete ${INSTANCE_NAME} --zone ${ZONE} --project ${PROJECT}

EOF
