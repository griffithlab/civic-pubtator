import codecs
import gzip
import json
import re
import sys

import entities 

entities_filenames = list()
entities_filenames.append("extracted/entities_manual.json.gz")
entities_filenames.append("extracted/entities_MeSH2023.txt.gz")
entities_filenames.append("extracted/entities_UNII.txt.gz")
entities_filenames.append("extracted/entities_ChEBI.txt.gz")
entities_filenames.append("extracted/entities_DSSTox.txt.gz")
entities_filenames.append("extracted/entities_UMLS.txt.gz")
entities_filenames.append("extracted/entities_DO.txt.gz")
entities_filenames.append("extracted/entities_HPO.txt.gz")
entities_filenames.append("extracted/entities_MONDO.txt.gz")
entities_filenames.append("extracted/entities_NCBITaxon.txt.gz")
entities_filenames.append("extracted/entities_NCIMT.txt.gz")
entities_filenames.append("extracted/entities_NCIThesaurus.txt.gz")
entities_filenames.append("extracted/entities_MF.json")

identifier_mappings = dict()
name2ids = dict()

def main():
	mappings_filename = sys.argv[1] # "data/mappings_2023.tsv"
	print("mappings_filename = {}".format(mappings_filename))
	name2ids_filename = sys.argv[2] # "data/name2ids_2023.txt.gz"
	print("name2ids_filename = {}".format(name2ids_filename))
	load_mappings(mappings_filename)
	for filename in entities_filenames:
		load_entities(filename)
	write_name2ids(name2ids_filename)

def load_mappings(filename):
	with open(filename, "r") as file:
		for line in file:
			line = line.strip()
			if len(line) == 0:
				continue
			fields = line.split("\t")
			if len(fields) != 2:
				raise ValueError("Line \"{}\" does not have exactly 2 fields".format(line))
			identifier_mappings[fields[0]] = fields[1]

def load_entities(filename):
	print("Loading entities from " + filename)
	entities_dict = entities.read(filename)
	for key in entities_dict: 
		entity = entities_dict[key]
		id = entity["id"]
		id = identifier_mappings.get(id, id)
		names = entity.get("names")
		if names is None:
			continue
		for name in names:
			name = name.strip()
			if len(name) == 0:
				continue
			if not name in name2ids:
				name2ids[name] = set()
			name2ids[name].add(id)
	print("Loaded " + str(len(entities_dict)) + " entities")
	del entities_dict

def write_name2ids(filename):
	print("Writing names to ids file to " + filename)
	name2ids2 = dict()
	for name, ids in name2ids.items():
		name2ids2[name] = list(ids)
	# Open the file
	file = None
	if filename.endswith(".gz"):
		file = gzip.open(filename, 'wt', encoding="utf-8") 
	else:
		file = codecs.open(filename, 'w', encoding="utf-8") 
	json.dump(name2ids2, file, indent = 3)
	file.close()

if __name__ == '__main__':
    main()
