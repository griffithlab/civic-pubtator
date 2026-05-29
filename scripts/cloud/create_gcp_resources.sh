#!/bin/bash

SRC_DIR=$(dirname "$0")

function show_help {
    echo "$0 - Create/Destroy resources for civic-pubtator workflow"
    echo ""
    echo "usage: sh $0 COMMAND --project <PROJECT> --bucket <BUCKET> --ip-range <RANGE>"
    echo ""
    echo "commands:"
    echo "    init-project        Create required resources for the project. You'll almost always want this one."
    echo ""
    echo "arguments:"
    echo "    -h, --help     print this block"
    echo "    --bucket       name for the GCS bucket used by Cromwell"
    echo "    --project      name of your GCP project"
    echo "    --ip-range     block/range of acceptable IPs e.g. 172.16.0.0/24 or a single IP address e.g. 172.16.5.9/32 or a comma-seperated list of IPs/CIDRs."
    echo "    --gc-region    DEFAULT='us-central1'. For other regions, check: https://cloud.google.com/compute/docs/regions-zones"
    echo "    --retention    DEFAULT is none. For more option, check: https://cloud.google.com/storage/docs/gsutil/commands/mb#retention-policy"
    echo ""
    echo "example command:"
    echo ""
    echo "     ./create_gcp_resources.sh init-project --project griffith-lab --bucket civic-pubtator --ip-range '128.252.0.0/16,65.254.96.0/19'"
}

function die {
    printf '%s\n' "$1" >&2 && exit 1
}

COMMAND=$1; shift
if [[ ($COMMAND != "init-project") ]]; then
    show_help
    die "ERROR: invalid command - $COMMAND"
fi

while test $# -gt 0; do
    case $1 in
        -h|--help)
            show_help
            exit
            ;;
        --bucket*)
            if [ ! "$2" ]; then
                die 'ERROR: "--bucket" requires a non-empty argument.'
            else
                BUCKET=$2
                shift
            fi
            ;;
        --project*)
            if [ ! "$2" ]; then
                die 'ERROR: "--project" requires a non-empty argument.'
            else
                PROJECT=$2
                shift
            fi
            ;;
	--ip-range*)
	    if [ ! "$2" ]; then
		die 'ERROR: "--ip-range" requires a non-empty argument.'
	    else
		IP_RANGE=$2
		shift
	    fi
	    ;;
	--gc-region*)
	    if [ ! "$2" ]; then
		GC_REGION="us-central1"
	    else
		GC_REGION=$2
		shift
	    fi
       	    ;;
	--retention*)
	    if [ ! "$2" ]; then
		RETENTION=""
	    else
		RETENTION=$2
		shift
	    fi
       	    ;;
         *)
            break
            ;;
    esac
    shift
done

if [ -z $PROJECT ]; then
    die 'ERROR: "--project" must be set.'
fi
if [ -z $BUCKET ]; then
    die 'ERROR: "--bucket" must be set.'
fi
if [ -z $IP_RANGE ]; then
    die 'ERROR: "--ip-range" must be set.'
fi
if [ -z $GC_REGION ]; then
    GC_REGION="us-central1"
fi
if [ -z $RETENTION ]; then
    RETENTION=""
fi

case $COMMAND in
    "init-project")
        # Create service accounts
        sh $SRC_DIR/gcp_resources.sh $PROJECT $BUCKET $IP_RANGE $GC_REGION $RETENTION
        ;;
esac

cat <<EOF

Completed $COMMAND. Check stderr logs and make sure nothing unexpected
happened. Script optimistically executes and will relay gcloud's error on
redundant operations, e.g. creating a resource that already exists.

EOF
