import datetime
import json
import os  
import sys

from dictionary_normalizer2 import DictionaryNormalizer2

def target_MESH(resource, accession):
	return resource == "MESH" and not accession.startswith("Q")

def target_CHEBI(resource, accession):
	return resource == "CHEBI"

# TODO Define filters for other resources
target2filter = dict()
target2filter["MESH"] = target_MESH
target2filter["CHEBI"] = target_CHEBI

if __name__ == "__main__":
	# TODO Allow multiple config files, to handle multiple entity types
	start = datetime.datetime.now()
	if len(sys.argv) != 3:
		print("Usage: <config> <output>")
		exit()
	config_filename = sys.argv[1]
	output_filename = sys.argv[2]

	# Load the configuration
	print("Loading configuration")
	with open(config_filename) as config_file:
		config = json.load(config_file)

	# Create the DictionaryNormalizer
	filter = target2filter[config["target_resource"]]
	normalizer = DictionaryNormalizer2(config, filter)
	print("Total init time = " + str(datetime.datetime.now() - start))

	print("Getting names")
	start = datetime.datetime.now()
	names = set()
	for name, ids in normalizer.name2ids.items():
		add = False
		for id in ids:
			fields = id.split(":")
			resource = fields[0]
			accession = fields[1]
			if target_MESH(resource, accession) or target_CHEBI(resource, accession):
				add = True
		if add:
			names.add(name)
	start = datetime.datetime.now()
	print("Processing {} names".format(len(names)))
	print("Elapsed = " + str(datetime.datetime.now() - start))

	start = datetime.datetime.now()
	with open(output_filename, "w") as output_file:
		for name_index, name in enumerate(names):
			target_entities, sieve = normalizer.normalize_mention(name)
			resolved = target_entities.intersection(normalizer.allowed_ids)
			output_file.write("{}\t{}\t{}\t{}\t{}\t{}\n".format(name, sieve, len(target_entities), target_entities, len(resolved), resolved))
			completed = name_index + 1
			if completed % 50000 == 0:
				elapsed = (datetime.datetime.now() - start).total_seconds()
				rate = completed / elapsed
				remaining = len(names) - completed
				estimated_time = remaining / rate
				print("completed = {}, rate = {}, remaining = {}, estimated_time = {}".format(completed, rate, remaining, estimated_time))
	print("Total processing time = " + str(datetime.datetime.now() - start))
	print("Done.")
	
