CP=libs/taggerOne.jar
CP=${CP}:libs/trove-3.0.3.jar
CP=${CP}:libs/dragontool.jar
CP=${CP}:libs/heptag.jar
CP=${CP}:libs/fastutil-7.0.6.jar
CP=${CP}:libs/jopt-simple-4.9.jar
CP=${CP}:libs/commons-math3-3.5.jar
CP=${CP}:libs/slf4j-api-1.7.20.jar
CP=${CP}:libs/slf4j-simple-1.7.20.jar
PR="-Dorg.slf4j.simpleLogger.defaultLogLevel=debug -Dorg.slf4j.simpleLogger.showThreadName=false -Dorg.slf4j.simpleLogger.showLogName=false -Dorg.slf4j.simpleLogger.logFile=System.out"
MODEL=$1
OPT="--evaluationDatasetConfig ncbi.taggerOne.dataset.PubtatorDataset|data/BC5CDR_TEST/CDR_TestSet.PubTator.joint.txt|data/BC5CDR_TEST/CDR_TestSet.pmids.txt|Chemical->Chemical,Disease->Disease|Chemical->Identify,Disease->Ignore|MESH"
OPT="${OPT} --modelInputFilename ${MODEL}"
OPT="${OPT} --useSentenceBreaker true"
OPT="${OPT} --abbreviationPostProcessingArgs 1|1|false"
OPT="${OPT} --consistencyPostProcessingArgs 10|2"
OPT="${OPT} --abbreviationSource ncbi.taggerOne.abbreviation.FileAbbreviationSource|data/BC5CDR_TEST/abbreviations.tsv"
OPT="${OPT} --analysisFilename analysis_BC5CDRC.html"

echo ${OPT}
java ${PR} -Xmx10G -Xms10G -cp ${CP} ncbi.taggerOne.EvaluateModel ${OPT}
