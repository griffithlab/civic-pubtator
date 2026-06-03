import codecs
import datetime

import entities

entites_filename="extracted/entities_DO.txt.gz"
obo_filename="downloads/HumanDO.obo"

entities_dict = dict()

id2parents = dict()
id2keep = dict()
id2keep["DOID:4"] = True # Disease

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
					fields = line[index2 + 2:].split(" ")
					if fields[1].startswith("["):
						# print("Found synonym name \"" + name + "\"")
						names.add(name)
					elif fields[1] == "IUPAC_NAME":
						# print("Found IUPAC name \"" + name + "\"")
						names.add(name)
					elif fields[1] == "INN":
						# print("Found INN name \"" + name + "\"")
						names.add(name)
					elif fields[1] == "BRAND_NAME":
						# print("Found brand name \"" + name + "\"")
						names.add(name)
					else:
						print("WARN Ignoring type \"" + fields[1] + "\"")
				elif line.startswith("property_value: "):
					fields = line.split(" ");
					value = fields[2]
					if fields[1]  == "exactMatch":
						# print("Found exactMatch \"" + value + "\"")
						xrefs.add(value)
					elif fields[1]  == "narrowMatch":
						# print("Found narrowMatch \"" + value + "\"")
						xrefs.add(value)
					elif fields[1]  == "broadMatch":
						# print("Found broadMatch \"" + value + "\"")
						xrefs.add(value)
					else:
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
					if resource == "DOID":
						parents.add(parent)
						if not id in id2parents:
							id2parents[id] = set()
						id2parents[id].add(parent)
						#print("Adding " + parent + " as parent of " + id)
					else:
						print("WARN parent resource \"" + resource + "\" is not DOID") 
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
resource_map["UMLS_CUI"] = "UMLS" # count = 6742
resource_map["NCI"] = "NCI" # count = 4717
resource_map["OMIM"] = "OMIM" # count = 4648
resource_map["ICD10CM"] = "ICD10CM" # count = 4221
resource_map["SNOMEDCT_US_2018_03_01"] = "SCTID" # count = 3916
resource_map["SNOMEDCT_US_2019_09_01"] = "SCTID"
resource_map["SNOMEDCT_US_2020_03_01"] = "SCTID"
resource_map["SNOMEDCT_US_2020_09_01"] = "SCTID"
resource_map["SNOMEDCT_US_2021_09_01"] = "SCTID"
resource_map["SNOMEDCT_US_2022_06_30"] = "SCTID"
resource_map["SNOMEDCT_US_2021_07_31"] = "SCTID"
resource_map["SNOMEDCT_US_2022_03_01"] = "SCTID"
resource_map["SNOMEDCT_US_2022_12_31"] = "SCTID"
resource_map["SNOMEDCT_US_2022_07_31"] = "SCTID"
resource_map["MESH"] = "MESH" # count = 3377
resource_map["ICD9CM"] = "ICD9CM" # count = 2596
resource_map["NCI2004_11_17"] = "NCI" # count = 1877
resource_map["GARD"] = "GARD" # count = 1724 (?)
resource_map["ORDO"] = "ORDO" # count = 1555 (?)
resource_map["MTHICD9_2006"] = "MTHICD9" # count = 489
resource_map["ICD9CM_2006"] = "ICD9CM" # count = 428
resource_map["CSP2005"] = None # count = 3287
resource_map["EFO"] = "EFO" # count = 132 (?)
resource_map["MTH"] = "MTH" # count = 100
resource_map["KEGG"] = "KEGG" # count = 39
resource_map["MEDDRA"] = "MEDDRA" # count = 19
resource_map["ICDO"] = "ICDO" # count = 12
resource_map["SNOMEDCT_US_2018_09_01"] = "SCTID" # count = 4
resource_map["SNOMED_CT_US_2018_03_01"] = "SCTID" # count = 3
resource_map["SNOMEDCT_US_2019_03_01"] = "SCTID" # count = 3
resource_map["SNOMEDCT_US_2022_09_01"] = "SCTID" # count = 3
resource_map["stedman"] = None # count = 1
resource_map["SNOMECT"] = "SCTID" # count = 1
resource_map["ICD-O"] = "ICDO" # count = 1
resource_map["ICD-10"] = "ICD10" # count = 1
resource_map["ICD11"] = "ICD11"
resource_map["DERMO"] = None # count = 1

if __name__ == '__main__':
    main()
