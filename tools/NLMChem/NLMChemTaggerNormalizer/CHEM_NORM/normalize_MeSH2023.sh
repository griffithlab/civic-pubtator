#source .env/bin/activate
export PYTHONIOENCODING=utf8
#export PYTHONPATH=.:$PYTHONPATH

date

INPUT=$(realpath ${1})
FORMAT=${2}
ABBR=$(realpath ${3})
OUTPUT=$(realpath ${4})

echo "INPUT=${INPUT}"
echo "ABBR=${ABBR}"
echo "OUTPUT=${OUTPUT}"

if [[ -d ${INPUT} ]]; then
	echo "is dir"
	mkdir -p ${OUTPUT}
	#rm -f ${OUTPUT}/*
fi

python -u src/normalize.py config_CHEM_MESH_2023.json ${FORMAT} ${ABBR} ${INPUT} ${OUTPUT}
#deactivate

date
echo "Done."
