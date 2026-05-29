#!/usr/bin/bash

PROJECT=$1
BUCKET=$2
IP_RANGE=$3
GC_REGION=$4
RETENTION=$5

NETWORK=civic-pubtator
SUBNET=civic-pubtator-default

# WASHU_CIDR="128.252.0.0/16"
# WASHU2_CIDR="65.254.96.0/19"

# Network
gcloud compute networks create $NETWORK \
       --project=$PROJECT \
       --subnet-mode=custom

# Subnet
gcloud compute networks subnets create $SUBNET \
       --project=$PROJECT \
       --range="10.10.0.0/16" \
       --region=$GC_REGION \
       --network=$NETWORK

# Firewall
gcloud compute firewall-rules create $NETWORK-allow-ssh \
       --project=$PROJECT \
       --source-ranges $IP_RANGE \
       --network=$NETWORK \
       --allow tcp:22

# Bucket
[ ! -z $RETENTION ] && gsutil mb --retention $RETENTION gs://$BUCKET
gsutil mb -p $PROJECT -b on gs://$BUCKET
gsutil pap set enforced gs://$BUCKET
