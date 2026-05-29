#!/usr/bin/env bash

SRC_DIR="$(dirname "${BASH_SOURCE[0]}")"

NETWORK=civic-pubtator
SUBNET=civic-pubtator-default

show_help () {
    cat <<EOF
$0 - Start a new Cromwell VM instance
usage: $0 INSTANCE_NAME [--argument value]*

arguments:
-h, --help           prints this block and immediately exits
--project            GCP project name
--machine-type       GCP machine type for the instance. DEFAULT e2-standard-2
--zone               DEFAULT us-central1-c. For options, visit: https://cloud.google.com/compute/docs/regions-zones 

Additional arguments are passed directly to gsutil compute instances
create command. For more information on those arguments, check that commands
help page with

    gcloud compute instances create --help

EOF
}

die () {
    printf '%s\n\n' "$1" >&2
    show_help
    exit 1
}


INSTANCE_NAME=$1
if [ -z $INSTANCE_NAME ]; then
    show_help
    exit 1
fi
shift


while test $# -gt 0; do
    case $1 in
        -h|-\?|--help)
            show_help
            exit 0
            ;;
        --project*)
            if [ ! "$2" ]; then
                die 'Error: "--project" requires a string argument for the GCP project name used'
            else
                PROJECT=$2
                shift
            fi
            ;;
        --machine-type*)
            if [ ! "$2" ]; then
                die 'ERROR: "--machine-type" requires a string argument.'
            else
                MACHINE_TYPE=$2
                shift
            fi
            ;;
        --zone*)
            if [ ! "$2" ]; then
		        ZONE="us-central1-c"
            else
                ZONE=$2
                shift
            fi
            ;;
        *)
            break
            ;;
    esac
    shift
done

MACHINE_TYPE=${MACHINE_TYPE:-"e2-standard-2"}

[ -z $PROJECT          ] && die "Missing argument --project"
[ -z $ZONE             ] && ZONE="us-central1-c"

# $@ indicates the ability to add any of the other flags that come with gcloud compute instances creat
# for a full account, visit https://cloud.google.com/sdk/gcloud/reference/compute/instances/create
gcloud compute instances create $INSTANCE_NAME \
       --project $PROJECT \
       --image-family debian-11 \
       --image-project debian-cloud \
       --zone $ZONE \
       --machine-type=$MACHINE_TYPE \
       --scopes=cloud-platform \
       --network=$NETWORK --subnet=$SUBNET \
       --metadata-from-file=startup-script=$SRC_DIR/gcp_server_startup.py \
       $@

cat <<EOF
To use this instance, SSH into it via:

    gcloud compute ssh $INSTANCE_NAME

To view startup script progress once logged into it:

    journalctl -u google-startup-scripts -f

To delete the instance when you're done:

    gcloud compute instances delete $INSTANCE_NAME

EOF
exit 0

