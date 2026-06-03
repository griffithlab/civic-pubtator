import datetime
import json
import os  
import sys

from abbreviations import AbbreviationExpander
from dictionary_normalizer import DictionaryNormalizer
from document_processor import DocumentProcessor
from document_processor_PubTator import PubTatorDocumentProcessor
from document_processor_TSV import TSVDocumentProcessor

def target_MESH(resource, accession):
	return resource == "MESH" and not accession.startswith("Q")

def target_CHEBI(resource, accession):
	return resource == "CHEBI"

def target_MONDO(resource, accession):
	return resource == "MONDO"

# TODO Define filters for other resources
target2filter = dict()
target2filter["MESH"] = target_MESH
target2filter["CHEBI"] = target_CHEBI
target2filter["MONDO"] = target_MONDO

if __name__ == "__main__":
	# TODO Allow multiple config files, to handle multiple entity types
	start = datetime.datetime.now()
	if len(sys.argv) != 6:
		print("Usage: <config> <format> <abbreviations> <input> <output>")
		exit()
	config_filename = sys.argv[1]
	input_format = sys.argv[2].lower()
	abbr_path = sys.argv[3]
	input_path = sys.argv[4]
	output_path = sys.argv[5]

	# Load the configuration
	print("Loading configuration")
	with open(config_filename) as config_file:
		config = json.load(config_file)

	# Load the abbreviation frequency file
	if "abbr_freq_filename" in config:
		print("Loading abbreviation frequency file")
		with open(config["abbr_freq_filename"], "r") as abbr_freq_file:
			abbr_freq_dict = json.load(abbr_freq_file)
	else:
		print("Skipping abbreviation frequency file")
		abbr_freq_dict = dict()
	abbr = AbbreviationExpander(abbr_freq_dict)
	
	# Create the DictionaryNormalizer
	filter = target2filter[config["target_resource"]]
	normalizer = DictionaryNormalizer(config, filter)
	
	# Create the DocumentProcessor
	type2normalizer = dict()
	type2normalizer[config["entity_type"]] = normalizer
	if input_format == "pubtator":
		doc_processor = PubTatorDocumentProcessor(type2normalizer, abbr)
	elif input_format == "biocxml":
		doc_processor = DocumentProcessor(type2normalizer, abbr)
	elif input_format == "tsv":
		doc_processor = TSVDocumentProcessor(type2normalizer, abbr)
	else:
		raise ValueError("Unknown format: {}".format(input_format))
	
	# Load the abbreviations
	print("Loading abbreviations")
	abbr.load(abbr_path)
	
	print("Total init time = " + str(datetime.datetime.now() - start))

	# Process
	start = datetime.datetime.now()
	if os.path.isdir(input_path):
		if not os.path.isdir(output_path):
			raise RuntimeError("If input path is a directory then output path must be a directory: " + output_path)
		print("Processing directory " + input_path)
		# Process any xml files found
		dir = os.listdir(input_path)
		for item in dir:
			input_filename = input_path + "/" + item
			output_filename = output_path + "/" + item
			if os.path.isfile(input_filename):
				print("Processing file " + input_filename + " to " + output_filename)
				doc_processor.process_file(input_filename, output_filename)
	elif os.path.isfile(input_path):
		# TODO If output_path exists, it must be a file
		# TODO If output_path does not exist, then its location must be a directory that exists
		if os.path.isdir(output_path):
			raise RuntimeError("If input path is a file then output path may not be a directory: " + output_path)
		print("Processing file " + input_path + " to " + output_path)
		# Process directly
		doc_processor.process_file(input_path, output_path)
	else:  
		raise RuntimeError("Path is not a directory or normal file: " + input_path)
	print("Total processing time = " + str(datetime.datetime.now() - start))

	print("Done.")
	
