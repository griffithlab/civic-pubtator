import gzip
import sys
import json
import collections

def main():
	mappings_filename = sys.argv[1]
	predictions_filename = sys.argv[2]
	output_filename = sys.argv[3]
	pairs = set()
	pairs.update(load_mappings(mappings_filename))
	pairs.update(load_predictions(predictions_filename))

	# Determine the highest confidence mapping for each identifier
	id_resource2confidence = dict()
	for source_ID, target_ID, confidence in pairs:
		id_resource1 = (source_ID, target_ID.split(":")[0])
		if not id_resource1 in id_resource2confidence:
			id_resource2confidence[id_resource1] = confidence
		elif id_resource2confidence[id_resource1] < confidence:
			id_resource2confidence[id_resource1] = confidence
		id_resource2 = (target_ID, source_ID.split(":")[0])
		if not id_resource2 in id_resource2confidence:
			id_resource2confidence[id_resource2] = confidence
		elif id_resource2confidence[id_resource2] < confidence:
			id_resource2confidence[id_resource2] = confidence
	
	entity_dict = dict()
	for source_ID, target_ID, confidence in pairs:
		if confidence >= id_resource2confidence[(source_ID, target_ID.split(":")[0])]:
			if not source_ID in entity_dict:
				entity_dict[source_ID] = {"id": source_ID, "xrefs": set()}
			entity_dict[source_ID]["xrefs"].add(target_ID)
		if confidence >= id_resource2confidence[(target_ID, source_ID.split(":")[0])]:
			if not target_ID in entity_dict:
				entity_dict[target_ID] = {"id": target_ID, "xrefs": set()}
			entity_dict[target_ID]["xrefs"].add(source_ID)
	entity_dict2 = {id: {"id": id, "xrefs": list(entity["xrefs"])} for id, entity in entity_dict.items()}
	if output_filename.endswith(".gz"):
		file = gzip.open(output_filename, 'wt', encoding="utf-8") 
	else:
		file = open(output_filename, 'w') 
	# Dump json to file
	json.dump(entity_dict2, file, indent = 3)
	file.close()
	ambiguous_count = 0
	for id, entity in entity_dict2.items():
		resource_counter = collections.Counter()
		for xref in entity["xrefs"]:
			resource = xref.split(":")[0]
			resource_counter[resource] += 1
		for resource, count in resource_counter.items():
			if count > 1:
				ambiguous_count += 1
				print("WARN: ID {} maps ambiguously to resource {}".format(id, resource))
	print("Total number of identifiers: {}".format(len(entity_dict)))
	print("Total number of mappings: {}".format(2 * len(pairs)))
	print("Total number of mappings: {}".format(sum(len(entity["xrefs"]) for entity in entity_dict.values())))
	print("Total number of mappings: {}".format(sum(len(entity["xrefs"]) for entity in entity_dict2.values())))
	print("Number of ambiguous mappings: {}".format(ambiguous_count))
	print("Done.")

def load_mappings(filename):
	pairs = set()
	with open(filename) as file:
		next(file)
		for line in file:
			fields = line.split("\t")
			source_prefix = fields[0].strip()
			source_identifier = fields[1].strip()
			#source_name = fields[2].strip()
			relation = fields[3].strip()
			target_prefix = fields[4].strip()
			target_identifier = fields[5].strip()
			#target_name = fields[6].strip()
			#type = fields[7].strip()
			#source = fields[8].strip()
			#prediction_type = fields[9].strip()
			#prediction_source = fields[10].strip()
			#prediction_confidence = fields[11].strip()
			if relation != "skos:exactMatch":
				continue
			source_ID = get_ID(source_prefix, source_identifier)
			target_ID = get_ID(target_prefix, target_identifier)
			if source_ID is None or target_ID is None:
				continue
			if source_ID < target_ID:
				pairs.add((source_ID, target_ID, 1.0))
			else:
				pairs.add((target_ID, source_ID, 1.0))
	return pairs
			
def load_predictions(filename):
	pairs = set()
	with open(filename) as file:
		next(file)
		for line in file:
			fields = line.split("\t")
			source_prefix = fields[0].strip()
			source_identifier = fields[1].strip()
			#source_name = fields[2].strip()
			relation = fields[3].strip()
			target_prefix = fields[4].strip()
			target_identifier = fields[5].strip()
			#target_name = fields[6].strip()
			#type = fields[7].strip()
			confidence = fields[8].strip()
			#source = fields[9].strip()
			if relation != "skos:exactMatch":
				continue
			source_ID = get_ID(source_prefix, source_identifier)
			target_ID = get_ID(target_prefix, target_identifier)
			if source_ID is None or target_ID is None:
				continue
			if source_ID < target_ID:
				pairs.add((source_ID, target_ID, float(confidence)))
			else:
				pairs.add((target_ID, source_ID, float(confidence)))
	return pairs

def get_ID(prefix, identifier):
	resource = resource_map.get(prefix)
	if resource is None:
		return None
	if not identifier.startswith(resource + ":"):
		return resource + ":" + identifier
	return identifier

resource_map = dict()
resource_map["mesh"] = "MESH" # count = 43431
resource_map["chebi"] = "CHEBI" # count = 14789
resource_map["ncit"] = "NCI" # count = 12663
resource_map["uniprot"] = None # count = 11348
resource_map["doid"] = "DOID" # count = 4204
resource_map["wikipathways"] = None # count = 3918
resource_map["umls"] = "UMLS" # count = 2532
resource_map["hgnc"] = "HGNC" # count = 1469
resource_map["go"] = "GO" # count = 1154
resource_map["efo"] = None # count = 976
resource_map["ccle"] = None # count = 690
resource_map["hp"] = "HP" # count = 385
resource_map["reactome"] = None # count = 364
resource_map["mondo"] = "MONDO" # count = 284
resource_map["kegg.pathway"] = None # count = 275
resource_map["uberon"] = None # count = 214
resource_map["idomal"] = None # count = 195
resource_map["agrovoc"] = None # count = 142
resource_map["agro"] = None # count = 142
resource_map["cellosaurus"] = None # count = 114
resource_map["uniprot.chain"] = None # count = 107
resource_map["pr"] = None # count = 100
resource_map["cl"] = None # count = 82
resource_map["ido"] = None # count = 76
resource_map["vo"] = None # count = 53
resource_map["apollosv"] = None # count = 45
resource_map["vsmo"] = None # count = 31
resource_map["ncbiprotein"] = None # count = 26
resource_map["ncbitaxon"] = "NCBITaxon" # count = 18
resource_map["pubchem.compound"] = "PUBCHEM_CID" # count = 17
resource_map["oae"] = None # count = 9
resource_map["cido"] = None # count = 8
resource_map["vido"] = None # count = 7
resource_map["idocovid19"] = None # count = 7
resource_map["pato"] = None # count = 6
resource_map["obi"] = None # count = 6
resource_map["maxo"] = None # count = 4
resource_map["depmap"] = None # count = 4
resource_map["cemo"] = None # count = 4
resource_map["dron"] = None # count = 3
resource_map["stato"] = None # count = 2
resource_map["opmi"] = None # count = 2
resource_map["obo"] = None # count = 2
resource_map["envo"] = None # count = 2
resource_map["dc"] = None # count = 2
resource_map["caro"] = None # count = 2
resource_map["bto"] = None # count = 2
resource_map["bfo"] = None # count = 2
resource_map["pfam"] = None # count = 1
resource_map["pco"] = None # count = 1
resource_map["ogms"] = None # count = 1
resource_map["ogg"] = None # count = 1
resource_map["oboinowl"] = None # count = 1
resource_map["ndfrt"] = None # count = 1
resource_map["nbo"] = None # count = 1
resource_map["mpath"] = None # count = 1
resource_map["miro"] = None # count = 1
resource_map["iao"] = None # count = 1
resource_map["fma"] = None # count = 1
resource_map["commoncoreontology"] = None # count = 1

if __name__ == '__main__':
    main()
