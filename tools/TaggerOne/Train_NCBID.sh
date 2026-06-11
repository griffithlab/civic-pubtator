echo TrainModel.sh $*
CP=libs/taggerOne.jar
CP=${CP}:libs/trove-3.0.3.jar
CP=${CP}:libs/dragontool.jar
CP=${CP}:libs/heptag.jar
CP=${CP}:libs/fastutil-7.0.6.jar
CP=${CP}:libs/commons-math3-3.5.jar
CP=${CP}:libs/jopt-simple-4.9.jar
CP=${CP}:libs/ojalgo-39.0.jar
CP=${CP}:libs/slf4j-api-1.7.20.jar
CP=${CP}:libs/slf4j-simple-1.7.20.jar
PR="-Dorg.slf4j.simpleLogger.defaultLogLevel=debug -Dorg.slf4j.simpleLogger.showThreadName=false -Dorg.slf4j.simpleLogger.showLogName=false -Dorg.slf4j.simpleLogger.logFile=System.out"
REGULARIZATION=$1
MAX_STEP_SIZE=$2
MODEL=$3
OPT="--entityTypes Disease"
OPT="${OPT} --lexiconNamespaces MESH|OMIM" 
OPT="${OPT} --trainingDatasetConfig ncbi.taggerOne.dataset.PubtatorDataset|data/NCBID/Corpus.txt|data/NCBID/NCBI_corpus_training_PMIDs.txt|SpecificDisease->Disease,DiseaseClass->Disease,Modifier->Disease,CompositeMention->Disease|Disease->Identify|MESH"
OPT="${OPT} --holdoutDatasetConfig ncbi.taggerOne.dataset.PubtatorDataset|data/NCBID/Corpus.txt|data/NCBID/NCBI_corpus_development_PMIDs.txt|SpecificDisease->Disease,DiseaseClass->Disease,Modifier->Disease,CompositeMention->Disease|Disease->Identify|MESH"
OPT="${OPT} --lexiconConfig ncbi.taggerOne.lexicon.loader.CTDDiseaseLexiconMappingsLoader|Disease|data/NCBID/CTD_diseases.tsv"
OPT="${OPT} --abbreviationSource ncbi.taggerOne.abbreviation.FileAbbreviationSource|data/NCBID/abbreviations.tsv"
OPT="${OPT} --entityTokenizerClass ncbi.taggerOne.util.tokenization.SimpleTokenizer"
OPT="${OPT} --textInstanceTokenizerClass ncbi.taggerOne.util.tokenization.SimpleTokenizer"
OPT="${OPT} --stemmerClass ncbi.taggerOne.processing.string.PorterStemmer"
OPT="${OPT} --regularization ${REGULARIZATION}"
OPT="${OPT} --maxStepSize ${MAX_STEP_SIZE}"
OPT="${OPT} --topNLabelings 1"
OPT="${OPT} --topNNormalization 1"
OPT="${OPT} --iterationsPastLastImprovement 10"
OPT="${OPT} --maxTrainingIterations 100"
OPT="${OPT} --deterministicOrdering false"
OPT="${OPT} --averageRecognitionModel true"
OPT="${OPT} --averageNormalizationModels true"
OPT="${OPT} --modelOutputFilename ${MODEL}"
echo ${OPT}
java ${PR} -Xmx40G -Xms40G -cp ${CP} ncbi.taggerOne.TrainModel ${OPT}
HOSTNAME="$(hostname)"
date | mail -s "Training has completed on $HOSTNAME" robert.leaman@nih.gov
date | mail -s "Training has completed on $HOSTNAME" mail@robertleaman.net
