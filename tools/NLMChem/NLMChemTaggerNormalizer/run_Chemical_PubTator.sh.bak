set -e
INPUT=$(realpath ${1})
ABBR=$(realpath ${2})
OUTPUT=$(realpath ${3})
BASE_DIR=$(pwd)
CHEMNORM_DIR="${BASE_DIR}/CHEM_NORM"
mkdir -p ${OUTPUT}
cd ${CHEMNORM_DIR}
./normalize_MeSH2023.sh ${INPUT} PubTator ${ABBR} ${OUTPUT}