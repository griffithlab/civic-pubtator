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

	# Flatten the normalization
	
	name2norm = dict()

	# ptlookup
	print("Starting ptlookup")
	start = datetime.datetime.now()
	for p_template, names in normalizer.p_template2names.items():
		ids = set()
		for name in names:
			if name in normalizer.name2ids:
				ids.update(normalizer.name2ids[name])
		target_ids = normalizer.filter_nontarget(ids)
		for name in names:
			if len(target_ids) > 0:
				name2norm[name] = (target_ids, 2)
			name2norm[name] = normalizer.filter_nontarget(ids)
	print("Elapsed = " + str(datetime.datetime.now() - start))

	# ctlookup
	print("Starting ctlookup")
	start = datetime.datetime.now()
	for c_template, names in normalizer.c_template2names.items():
		ids = set()
		for name in names:
			if name in normalizer.name2ids:
				ids.update(normalizer.name2ids[name])
		target_ids = normalizer.filter_nontarget(ids)
		for name in names:
			if len(target_ids) > 0:
				name2norm[name] = (target_ids, 1)
			name2norm[name] = normalizer.filter_nontarget(ids)
	print("Elapsed = " + str(datetime.datetime.now() - start))

	# nlookup
	print("Starting nlookup")
	start = datetime.datetime.now()
	for name, ids in normalizer.name2ids.items():
		target_ids = normalizer.filter_nontarget(ids)
		if len(target_ids) > 0:
			name2norm[name] = (target_ids, 0)
	print("Elapsed = " + str(datetime.datetime.now() - start))

	start = datetime.datetime.now()
	with open(output_filename, "w") as output_file:
		for name_index, name in enumerate(names):
			target_entities, sieve = normalizer.normalize_mention(name)
			output_file.write("{}\t{}\t{}\t{}\n".format(name, len(target_entities), sieve, target_entities))
			if name_index % 1000 == 0:
				elapsed = (datetime.datetime.now() - start).total_seconds()
				completed = name_index + 1
				rate = completed / elapsed
				remaining = len(names) - completed
				estimated_time = remaining / rate
				print("completed = {}, rate = {}, remaining = {}, estimated_time = {}".format(completed, rate, remaining, estimated_time))
	print("Total processing time = " + str(datetime.datetime.now() - start))
	print("Done.")
	
 