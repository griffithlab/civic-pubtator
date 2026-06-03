import codecs
import datetime

import entities

entites_filename="extracted/entities_MONDO.txt.gz"
obo_filename="downloads/mondo.obo"

entities_dict = dict()

id2parents = dict()
id2keep = dict()
id2keep["MONDO:0000001"] = True # Disease
id2keep["MONDO:0042489"] = True # Disease susceptibility
#id2keep["MONDO:0020186"] = True # obsolete eyebrow hypertrophy
id2keep["MONDO:0021125"] = False # Disease characteristic

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
					index1 = line.find("\"")
					index2 = line.find("\"", index1 + 1)
					name = line[index1 + 1:index2]
					fields = line[index2 + 2:].split(" ")
					if fields[1].startswith("["):
						# print("Found synonym name \"" + name + "\"")
						names.add(name)
					elif fields[1] == "DEPRECATED":
						names.add(name)
					elif fields[1] == "AMBIGUOUS":
						names.add(name)
					elif fields[1] == "ABBREVIATION":
						names.add(name)
					elif fields[1] == "MISSPELLING":
						names.add(name)
					else:
						print("WARN Ignoring type \"" + fields[1] + "\"")
				elif line.startswith("property_value: "):
					fields = line.split(" ");
					type = fields[1]
					value = fields[2]
					if fields[1] == "exactMatch" or fields[1] == "narrowMatch" or fields[1] == "closeMatch" or fields[1] == "broadMatch" or fields[1] == "relatedMatch":
						# print("Found XRef property \"" + value + "\"")
						if value.startswith("http://") or value.startswith("https://"):
							# TODO Process as http resource
							resource = value.rsplit("/", 1)[0]					
							accession = value[len(resource) + 1:]
							if resource in http_resource_map:
								resource = http_resource_map[resource]
							else:
								print("WARN resource \"" + resource + "\" is unknown") 
								resource = None
							if not resource is None:
								xrefs.add(resource + ":" + accession)
						else:
							# Process as normal XRef
							resource = value.split(":")[0]					
							accession = value[len(resource) + 1:]
							if resource in resource_map:
								resource = resource_map[resource]
							else:
								print("WARN resource \"" + resource + "\" is unknown") 
								resource = None
							if not resource is None:
								xrefs.add(resource + ":" + accession)
					elif fields[1] == "IAO:0000233" or fields[1] == "seeAlso" or fields[1] == "IAO:0000231" or fields[1] == "IAO:0000589" or fields[1] == "RO:0002175" or fields[1] == "IAO:0006012":
						# print("Found ignorable property \"" + value + "\"")
						pass
					else:
						# Unknow property, warn
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
					if resource == "MONDO":
						parents.add(parent)
						if not id in id2parents:
							id2parents[id] = set()
						id2parents[id].add(parent)
						#print("Adding " + parent + " as parent of " + id)
					else:
						print("WARN parent resource \"" + resource + "\" is not MONDO") 
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
resource_map["UMLS"] = "UMLS" # count = 18606
resource_map["ICD10"] = "ICD10" # count = 11448
resource_map["Orphanet"] = "ORDO" # count = 8996
resource_map["DOID"] = "DOID" # count = 8494
resource_map["MESH"] = "MESH" # count = 8173
resource_map["OMIM"] = "OMIM" # count = 7996
resource_map["SCTID"] = "SCTID" # count = 6939
resource_map["NCIT"] = "NCI" # count = 5519
resource_map["GARD"] = "GARD" # count = 2833
resource_map["ICD9"] = "ICD9" # count = 2814
resource_map["EFO"] = "EFO" # count = 2248
resource_map["COHD"] = "COHD" # count = 1598
resource_map["MedDRA"] = "MDR" # count = 1474
resource_map["HP"] = "HP" # count = 508
resource_map["OMIMPS"] = "OMIM" # count = 383
resource_map["DC"] = "DC" # count = 190
resource_map["Wikipedia"] = None # count = 83
resource_map["CSP"] = "CSP" # count = 39
resource_map["KEGG"] = "KEGG" # count = 37
resource_map["NIFSTD"] = "NIFSTD" # count = 18
resource_map["SCTID_2010_1_31"] = "SCTID" # count = 16
resource_map["RO"] = "RO" # count = 15
resource_map["PMID"] = None # count = 11
resource_map["ICD9CM"] = "ICD9CM" # count = 7
resource_map["ICD10CM"] = "ICD10CM" # count = 5
resource_map["SNOMEDCT_US_2016_03_01"] = "SCTID" # count = 4
resource_map["MP"] = None # count = 4
resource_map["MFOMD"] = None # count = 3
resource_map["Wikidata"] = None # count = 2
resource_map["UMLS_CUI"] = "UMLS" # count = 2
resource_map["OGMS"] = None # count = 2
resource_map["NCI"] = "NCI" # count = 2
resource_map["MEDGEN"] = "MEDGEN" # count = 2
resource_map["IDO"] = None # count = 2
resource_map["ICDCM10"] = "ICD10CM" # count = 2
resource_map["EV"] = None # count = 2
resource_map["https"] = None # count = 1
resource_map["http"] = None # count = 1
resource_map["UniProt"] = None # count = 1
resource_map["SNOWMEDCT"] = "SCTID" # count = 1
resource_map["ORDO"] = "ORDO" # count = 1
resource_map["OBI"] = None # count = 1
resource_map["NDFRT"] = "NDFRT" # count = 1
resource_map["NCiT"] = None # count = 1
resource_map["NCI_Metathesaurus"] = "NCI_Metathesaurus" # count = 1
resource_map["MeSH"] = "MESH" # count = 1
resource_map["MTH"] = "MTH" # count = 1
resource_map["MEDDRA"] = "MEDDRA" # count = 1
resource_map["GTR"] = "GTR" # count = 1
resource_map["DERMO"] = "DERMO" # count = 1
resource_map["BFO"] = "BFO" # count = 1
resource_map["ICDO"] = "ICDO" # count = 769
resource_map["ONCOTREE"] = "ONCOTREE" # count = 558
resource_map["ICD10EXP"] = "ICD10CM" # count = 86
resource_map["DECIPHER"] = "DECIPHER" # count = 61
resource_map["HGNC"] = "HGNC" # count = 55
resource_map["ICD10WHO"] = "ICD10CM" # count = 86


http_resource_map = dict()
http_resource_map["http://linkedlifedata.com/resource/umls/id"] = "UMLS" # 16627
http_resource_map["https://omim.org/entry"] = "OMIM" # 9313
http_resource_map["http://identifiers.org/snomedct"] = "SCTID" # 9048
http_resource_map["http://identifiers.org/mesh"] = "MESH" # 8099
http_resource_map["http://purl.bioontology.org/ontology/ICD10CM"] = "ICD10CM" # 7393
http_resource_map["http://identifiers.org/meddra"] = "MEDDRA" # 1485
http_resource_map["https://omim.org/phenotypicSeries"] = "OMIM" # 533
http_resource_map["http://identifiers.org/medgen"] = "MEDGEN" # 26
http_resource_map["https://icd.who.int/browse10/2019/en#"] = "ICD10CM" # 18

if __name__ == '__main__':
    main()
