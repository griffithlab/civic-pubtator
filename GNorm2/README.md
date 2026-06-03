# GNorm2
***
GNorm2 is a gene name recognition and normalization tool with optimized functions and customizable configuration to the user preferences. The GNorm2 integrates multiple deep learning-based methods and achieves state-of-the-art performance. GNorm2 is freely available to download for stand-alone usage.


## Content
- [Dependency package](#package)
- [Introduction of folders](#intro)
- [Running GNorm2](#pipeline)

## Dependency package
<a name="package"></a>
The codes have been tested using Python3.1 on CentOS. To install all dependencies automatically using the command:

    $ python3.11 -m venv env311
	$ source env311/bin/activate
	$ python3.11 -m pip install --upgrade pip
	$ pip3 install -r requirements.txt



## Introduction of folders
<a name="intro"></a>

- src_python
	- GeneNER: the codes for gene recognition
	- SpeAss: the codes for species assignment
- src_Java
	- GNormPluslib : the codes for gene normalization and species recogntion
- GeneNER_SpeAss_run.py: the script for runing pipeline
- GNormPlus.jar: the upgraded GNormPlus tools for gene normalization
- gnorm_trained_models:pre-trianed models and trained NER/SA models
	- bioformer-cased-v1.0: the original bioformer model
	- BiomedNLP-PubMedBERT-base-uncased-abstract: the original pubmedbert model
	- geneNER
		- GeneNER-Bioformer/PubmedBERT-Allset.h5: the Gene NER models trained by all datasets
		- GeneNER-Bioformer/PubmedBERT-Trainset.h5: the Gene NER models trained by the training set only
	- SpeAss
		- SpeAss-Bioformer/PubmedBERT-SG-Allset.h5: the Species Assignment models trained by all datasets
		- SpeAss-Bioformer/PubmedBERT-SG-Trainset.h5: the Species Assignment models trained by the trianing set only
	- stanza
		- downloaded stanza library for offline usage
- vocab: label files for the machine learning models of GeneNER and SpeAss
- Dictionary: The dictionary folder contains all required files for gene normalization
- CRF: CRF++ library (called by GNormPlus.sh)
- Library: Ab3P library
- tmp/tmp_GNR/tmp_SA/tmp_SR folders: temp folder
- input/output folders: input and output folders. BioC (abstract or full text) and PubTator (abstract only) formats are both avaliable.
- GNorm2.sh: the script to run GNorm2
- setup.GN.txt/setup.SR.txt/setup.txt the setup files for GNorm2.

## Running GNorm2
<a name="pipeline"></a>
Use our trained models (i.e., PubmedBERT/Bioformer) for running Gene NER and Species Assignment by */src/GeneNER_SpeAss_run.py*.

The file has 5 parameters:

- --infolder, -i, help="input folder"
- --NERmodel, -n, help="trained deep learning NER model file"
- --SAmodel, -s, help='trained deep learning species assignment model'
- --NERoutpath, -r, help="output folder to save the NER tagged results"
- --SAoutpath, -a, help="output folder to save the SA tagged results"

The input file format is [BioC(xml)](bioc.sourceforge.net) or [PubTator](https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/tmTools/Format.html) format with species recognition results. You can find some input examples in the /example/input/ folder .

1. Run pipeline (i.e., first Gene NER, then Species Assignment), when the two models are provided.

Run Example:

    $ python GeneNER_SpeAss_run.py -i ./example/input/ -n ./gnorm_trained_models/geneNER/GeneNER-Bioformer-Allset.h5 -s ./gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-Allset.h5 -r ./example/pipeline_ner_output/ -a ./example/pipeline_sa_output/

2. Run Gene NER only, when only the Gene NER model is provided.

Run Example:

    $ python GeneNER_SpeAss_run.py -i ./example/input/ -n ./gnorm_trained_models/geneNER/GeneNER-Bioformer-Allset.h5  -r ./example/ner_output/

3. Run Species Assignment only, when only the Species Assignment model is provided.

Run Example:

    $ python GeneNER_SpeAss_run.py -i ./example/ner_output/ -s ./gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-Allset.h5  -a ./example/sa_output/


## Acknowledgments
This research was supported by the Intramural Research Program of the National Library of Medicine (NLM), National Institutes of Health.