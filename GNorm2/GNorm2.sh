#!/bin/sh

export TF_USE_LEGACY_KERAS=1

#source env311/bin/activate
#export PATH=$PATH:/bin:/usr/bin
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$(pwd)/env311/lib
#sexport PATH=$(pwd)/env311/bin:$PATH

# Species Recognition
java -Xmx60G -Xms30G -jar GNormPlus.jar input tmp_SR setup.SR.txt

# Species Assignment + Gene Name Recognition
python3 GeneNER_SpeAss_run.py -i tmp_SR -r tmp_GNR -a tmp_SA -n gnorm_trained_models/GeneNER/GeneNER-Bioformer-BEST.h5 -s gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-BEST.h5

# Gene Normalization
java -Xmx60G -Xms30G -jar GNormPlus.jar tmp_SA output setup.GN.txt
