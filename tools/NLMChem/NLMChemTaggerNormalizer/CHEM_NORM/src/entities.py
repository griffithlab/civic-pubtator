import codecs
import gzip
import json
import re

id_key = "id"
types_key = "types"
names_key = "names"
parents_key = "parents"
xrefs_key = "xrefs"
key_sets = [types_key, names_key, parents_key, xrefs_key]

def write(entities_dict, filename):
	# Convert sets to lists
	entities_dict2 = dict()
	for entity_key, entity in entities_dict.items():
		entity2 = dict()
		entity2[id_key] = entity[id_key]
		for key in key_sets:
			if key in entity:
				if len(entity[key]) > 0:
					entity2[key] = list(entity[key])
		entities_dict2[entity_key] = entity2
	# Open the file
	file = None
	if filename.endswith(".gz"):
		file = gzip.open(filename, 'wt', encoding="utf-8") 
	else:
		file = codecs.open(filename, 'w', encoding="utf-8") 
	# Dump json to file
	json.dump(entities_dict2, file, indent = 3)
	file.close()

def read(filename):
	entities_dict = dict()
	if filename.endswith(".gz"):
		file = gzip.open(filename, 'rt', encoding="utf-8") 
	else:
		file = codecs.open(filename, 'r', encoding="utf-8")
	entities_dict = json.load(file)
	# TODO Convert sublists back into sets
	file.close()
	return entities_dict

def create(id, types, names, parents, xrefs):
	# TODO Modify to track what resource suggests what names
	# TODO Modify to track what resource asserts which synonyms 
	entity = dict()
	# TODO Verify ID matches resource:accession
	entity[id_key] = id
	# Normalize whitespace on names
	names2 = set()
	for name in names:
		name2 = name.strip()
		name2 = re.sub("\\s+", " ", name2)
		names2.add(name2)	
	# TODO Verify types
	entity[types_key] = types
	entity[names_key] = names2
	# TODO Verify parents match resource:accession
	entity[parents_key] = parents
	# TODO Verify xrefs match resource:accession
	entity[xrefs_key] = xrefs
	return entity
	# errors = verify(entity)
	#if len(errors) == 0:
	#	return entity
	#else:
	#	raise errors

