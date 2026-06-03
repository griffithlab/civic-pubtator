import codecs
import gzip
import json

import entities 

mappings_filename = "data/mappings_2023.tsv"
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

id2ids_filename="data/id2ids_2023.txt.gz"

# This is the maximum number of mappings a resource can have where one of its ids maps to multiple ids in the other resource for it to be considered granular enough to use as a pivot
max_pivot_duplication = 0.02

identifier_mappings = dict()

# This lists from each entity to all xrefs it is mapped to
primary2xrefs = dict()

# This is the list of resources that indicate a unique chemical
pivot_resources = set()

# Any primary ID mapping to an ID in a target resource is added directly
target_resources = {"MESH"}

# Maps from primary IDs (the ones listed as the ID for an entity with names) to target IDs
primary2target = dict()

def main():
	load_mappings(mappings_filename)
	for filename in entities_filenames:
		load_entities(filename)
		
	print("len(primary2xrefs) = " + str(len(primary2xrefs)))
	print("len(primary2xrefs.values()) = " + str(sum_item_len(primary2xrefs)))

	print("Doing pivot analysis")
	global pivot_resources
	do_pivot_analysis()
	print("Pivot resources: " + str(pivot_resources))
	#exit() # FIXME 
	#pivot_resources = ( "CAS", "UNII", "INCHIKEY", "INCHI", "SMILES", "EINECS" )
	print("Pivot resources: " + str(pivot_resources))
	
	print("Add primary mappings")
	add_primary_mappings()
	print("len(primary2target) = " + str(len(primary2target)))
	print("len(primary2target.values()) = " + str(sum_item_len(primary2target)))
		
	print("Add pivot mappings")
	pivot_ids = set()
	for id in primary2xrefs:
		resource = id.split(":")[0]
		if resource in pivot_resources:
			pivot_ids.add(id)
	print("len(pivot_ids) = " + str(len(pivot_ids)))
	for id1 in pivot_ids:
		synonym_ids = set()
		synonym_ids.add(id1)
		if id1 in primary2xrefs:
			synonym_ids.update(primary2xrefs[id1])
		# From IDs are the primary IDs - these are the ones that have names
		from_ids = set()
		# To IDs are the target IDs - these are the ones we want to link to
		to_ids = set()
		for id2 in synonym_ids:
			if id2 in primary2xrefs.keys():
				from_ids.add(id2)
			resource2 = id2.split(":")[0]
			if resource2 in target_resources:
				to_ids.add(id2)
		for id2 in from_ids:
			primary2target[id2].update(to_ids)
			primary2target[id2].discard(id2)

	print("len(primary2target) = " + str(len(primary2target)))
	print("len(primary2target.values()) = " + str(sum_item_len(primary2target)))

	write_id2ids(id2ids_filename)

def write_id2ids(filename):
	print("Writing id to ids file to " + filename)
	primary2target2 = dict()
	for id, to_ids in primary2target.items():
		# Warn if mapping not unique
		if len(to_ids) > 1:
			print("WARN ID " + id + " maps to " + str(len(to_ids)) + " target IDs: " + str(to_ids))
		ids_list = list(to_ids)
		primary2target2[id] = ids_list
	# Open the file
	if filename.endswith(".gz"):
		file = gzip.open(filename, 'wt', encoding="utf-8") 
	else:
		file = codecs.open(filename, 'w', encoding="utf-8") 
	json.dump(primary2target2, file, indent = 3)
	file.close()

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

def add_primary_mappings():
	for id, xrefs in primary2xrefs.items():
		synonym_ids = set()
		synonym_ids.add(id)
		synonym_ids.update(xrefs)
		# Gather target IDs
		to_ids = set()
		for id1 in synonym_ids:
			resource1 = id1.split(":")[0]
			if resource1 in target_resources:
				to_ids.add(id1)
		# Map from primary IDs to target IDs
		for id2 in synonym_ids:
			if id2 in primary2xrefs:
				if not id2 in primary2target:
					primary2target[id2] = set()
				primary2target[id2].update(to_ids)
				primary2target[id2].discard(id2)

def do_pivot_analysis():
	id2ids = dict()
	for id1, xrefs in primary2xrefs.items():
		# Add forward
		if not id1 in id2ids:
			id2ids[id1] = set()
		id2ids[id1].update(xrefs)
		# Add backward
		for xref in xrefs:
			if not xref in id2ids:
				id2ids[xref] = set()
			id2ids[xref].add(id1)
	print("len(id2ids) = " + str(len(id2ids)))
	print("len(id2ids.values()) = " + str(sum_item_len(id2ids)))
	resource2resources = dict()
	resource2total = dict()
	resource2duplicate = dict()
	for id1, xrefs in id2ids.items():
		resource1 = id1.split(":")[0]
		if not resource1 in resource2resources:
			resource2resources[resource1] = set()
			resource2total[resource1] = 0
			resource2duplicate[resource1] = 0
		added = set()
		for id2 in xrefs:
			resource2 = id2.split(":")[0]
			# Mappings between the same resource (e.g. retired IDs) don't count
			if resource1 != resource2:
				resource2resources[resource1].add(resource2)
				resource2total[resource1] += 1
				if resource2 in added:
					resource2duplicate[resource1] += 1
				added.add(resource2)
	# List the resources that map directly to a target resource
	direct_target_resources = set()
	for resource in target_resources:
		direct_target_resources.add(resource)
		mapped_resources = resource2resources[resource]
		direct_target_resources.update(mapped_resources)
	# Identify resources with acceptable duplication levels that can pivot to a direct target resource
	for resource, resources in resource2resources.items():
		#print("Resource {} maps to {}".format(resource, resources))
		total_count = resource2total[resource]
		duplicate_count = resource2duplicate[resource]
		duplication = duplicate_count / total_count
		target_overlap = direct_target_resources.intersection(resources)
		pivot = len(resources) > 1 and len(target_overlap) > 0 and duplication < max_pivot_duplication
		print(resource + "\t" + str(len(resources)) + "\t" + str(len(target_overlap)) + "\t" + str(total_count) + "\t" + str(duplicate_count) + "\t" + str(duplication) + "\t" + str(pivot))
		if pivot:
			pivot_resources.add(resource)

def load_entities(filename):
	print("Loading entities from " + filename)
	entities_dict = entities.read(filename)
	for id, entity in entities_dict.items():
		id = identifier_mappings.get(id, id)
		if not id in primary2xrefs:
			primary2xrefs[id] = set()
		if "xrefs" in entity:
			xrefs = entity["xrefs"]
			xrefs2 = {identifier_mappings.get(xref_id, xref_id) for xref_id in xrefs}
			primary2xrefs[id].update(xrefs2)

def sum_item_len(dict):
	len_sum = 0
	for value in dict.values():
		len_sum += len(value)
	return len_sum

if __name__ == '__main__':
    main()
