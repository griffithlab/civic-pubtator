This folder contains the scripts and code to run the Chemical normalization system initially designed for the NLMChem tagger. Input is in either BioC XML or PubTator format, output format is the same as the input format. The system runs only on CPU and does not use any deep learning. 

The normalize_MeSH2023.sh script normalizes the NER annotations for type Chemical to MeSH 2023.

These are the required inputs: 
-	$INPUT: Path of a single BioC XML file, or a folder containing a batch of BioC XML files to be processed. Annotations of type "Chemical" will be normalized to MeSH.
-	$FORMAT: Either "BioCXML" or "PubTator"
-	$ABBR: Path to the abbreviation information for the input articles. May be either a single file or a directory of files. Files ending in ".tsv" will be processed as a TSV file, ".xml" as a BioC XML file. All other files will be ignored.
-	$OUTPUT: Pathname of a single BioC XML file, or a folder for output BioC XML files


