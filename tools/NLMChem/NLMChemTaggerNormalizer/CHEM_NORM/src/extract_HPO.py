import codecs
import datetime

import entities

entites_filename="extracted/entities_HPO.txt.gz"
obo_filename="downloads/hp.obo"

entities_dict = dict()

id2parents = dict()
id2keep = dict()
id2keep["HP:0000001"] = False # All (ie root)
id2keep["HP:0000118"] = True # Phenotypic abnormality

def main():
	load_obo(obo_filename)
	print("Loaded " + str(len(entities_dict)) + " entities")
	
	entities_dict2 = dict()
	for id, entity in entities_dict.items():
		k = keep(id, set())
		if k is None:
			print("WARN No keep value for ID " + id)
		else:
			# Output all entities regardless, will be handled later during type inference
			entities_dict2[id] = entity
	print("Kept " + str(len(entities_dict2)) + " entities")

	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict2, entites_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def keep(id, history):
	if id in history:
		print("WARN ID " + id + " has a cycle: " + str(history))
		return None
	if id in id2keep:
		return id2keep[id]
	if not id in id2parents:
		print("WARN ID " + id + " does not have parents listed")
		return None
	parents = id2parents[id]
	keep_values = set()
	for parent in parents:
		history2 = set()
		history2.add(id)
		history2.update(history)
		keep2 = keep(parent, history2)
		keep_values.add(keep2)
	if len(keep_values) == 0:
		print("WARN ID " + id + " returned no keep values: " + str(keep_values))
		return None
	if len(keep_values) > 1:
		print("WARN ID " + id + " returned multiple keep values: " + str(keep_values))
		return None
	keep_values = list(keep_values)
	return keep_values[0]

def load_obo(filename):
	print("Loading file " + filename)
	with codecs.open(filename, 'r', encoding="utf-8") as f:
		state = 0 #Ignore
		id = ""
		names = set()
		parents = set()
		xrefs = set()
		for line in f:
			line = line.strip()
			# print(line)
			if line == "[Term]":
				# Output record
				if len(id) > 0:
					entities_dict[id] = entities.create(id, set(), names, parents, xrefs)
				# print("New record")
				state = 1 #Term
				id = ""
				names = set()
				parents = set()
				xrefs = set()
			elif line == "[Typedef]":
				state = 0 #Ignore
				id = ""
				names = set()
				parents = set()
				xrefs = set()
			elif state == 1:
				if line.startswith("id: "):
					id = line[4:]
					# print("Found id \"" + id + "\"")
				elif line.startswith("name: "):
					name = line[6:]
					# print("Found name \"" + name + "\"")
					names.add(name)
				elif line.startswith("alt_id: "):
					alt_id = line[8:]
					# print("Found alternate id \"" + alt_id + "\"")
					xrefs.add(alt_id)
				elif line.startswith("synonym: "):
					# synonym: "Al(-)" RELATED [IUPAC]
					# synonym: "aluminide(1-)" EXACT IUPAC_NAME [IUPAC]
					index1 = line.find("\"")
					index2 = line.rfind("\"")
					name = line[index1 + 1:index2]
					names.add(name)
				elif line.startswith("property_value: "):
					fields = line.split(" ");
					value = fields[2]
					value = value[1:len(value)-1]
					if fields[1].endswith("formula"):
						# print("Found formula \"" + value + "\"")
						xrefs.add("MF:" + value)
					elif fields[1].endswith("smiles"):
						# print("Found SMILES \"" + value + "\"")
						xrefs.add("SMILES:" + value)
					elif fields[1].endswith("inchikey"):
						# print("Found InChIKey \"" + value + "\"")
						xrefs.add("INCHIKEY:" + value)
					elif fields[1].endswith("inchi"):
						# print("Found InChI \"" + value + "\"")
						xrefs.add("INCHI:" + value)
					else:
						# Check for known properties to ignore, otherwise warn
						if not fields[1].endswith("creator") and not fields[1].endswith("date") and not fields[1].endswith("contributor"):
							print("WARN Ignoring property \"" + fields[1] + "\"")
				elif line.startswith("xref: "):
					fields = line.split(" ");
					#print("Found xref \"" + fields[1] + "\"")
					xref = fields[1]
					resource = xref.split(":")[0]					
					accession = xref[len(resource) + 1:]
					if resource in resource_map:
						resource = resource_map[resource]
					else:
						print("WARN resource \"" + resource + "\" is unknown") 
						resource = None
					if not resource is None:
						xrefs.add(resource + ":" + accession)
				elif line.startswith("is_a: "):
					fields = line.split(" ");
					#print("Found is_a \"" + fields[1] + "\"")
					parent = fields[1]
					resource = parent.split(":")[0]
					if resource == "HP":
						parents.add(parent)
						if not id in id2parents:
							id2parents[id] = set()
						id2parents[id].add(parent)
						#print("Adding " + parent + " as parent of " + id)
					else:
						print("WARN parent resource \"" + resource + "\" is not HP") 
				elif line == "is_obsolete: true":
					state = 0 #Ignore
					id = ""
					names = set()
					parents = set()
					xrefs = set()
		# Output record
		if len(id) > 0:
			entities_dict[id] = entities.create(id, set(), names, parents, xrefs)

resource_map = dict()
resource_map["UMLS"] = "UMLS" # count = 13167
resource_map["SNOMEDCT_US"] = "SCTID" # count = 4703
resource_map["SNOMED_CT"] = "SCTID" # count = 4703
resource_map["MSH"] = "MESH" # count = 2186
resource_map["MEDDRA"] = "MDR" # count = 93
resource_map["ICD-10"] = "ICD10" # count = 38
resource_map["ICD10"] = "ICD10" # count = 1
resource_map["ICD9"] = "ICD9" # count = 1
resource_map["MONDO"] = "MONDO" # count = 1
resource_map["pmid"] = None # count = 23
resource_map["EPCC"] = None # count = 13
resource_map["NCIT"] = "NCI" # count = 11
resource_map["MP"] = None # count = 10
resource_map["ORPHA"] = "ORPHA" # count = 6
resource_map["MPATH"] = None # count = 4
resource_map["PMID"] = None # count = 3
resource_map["ICD-O"] = "ICDO" # count = 3
resource_map["ICD-9"] = "ICD9" # count = 3
resource_map["DOI"] = None # count = 4
resource_map["http"] = None # count = 1
resource_map["DOID"] = "DOID" # count = 1
resource_map["Fyler"] = "Fyler" # count = 228; https://bioregistry.io/registry/fyler

if __name__ == '__main__':
    main()
