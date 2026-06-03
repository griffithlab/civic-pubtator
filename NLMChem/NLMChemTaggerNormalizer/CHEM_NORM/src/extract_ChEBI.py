import codecs
import datetime

import entities

entites_filename="extracted/entities_ChEBI.txt.gz"
obo_filename="downloads/chebi.obo"
chemicals_filename = "data/CHEBI/chem_ids_2023.tsv"

entities_dict = dict()

id2parents = dict()
id2keep = dict()
id2keep["CHEBI:24431"] = True # Chemical entity
id2keep["CHEBI:36342"] = True # Subatomic particle
id2keep["CHEBI:50906"] = False # Role

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
	print("Writing out chemical IDs")
	with open(chemicals_filename, "w") as chemicals_file:
		for id, k in id2keep.items():
			chemicals_file.write("{}\t{}\n".format(id, k))

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
	id2keep[id] = keep_values[0]
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
						if not fields[1].endswith("charge") and not fields[1].endswith("mass") and not fields[1].endswith("monoisotopicmass"):
							print("WARN Ignoring property \"" + fields[1] + "\"")
				elif line.startswith("xref: "):
					fields = line.split(" ");
					# print("Found xref \"" + fields[1] + "\"")
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
					# print("Found xref \"" + fields[1] + "\"")
					parent = fields[1]
					resource = parent.split(":")[0]
					if resource == "CHEBI":
						parents.add(parent)
						if not id in id2parents:
							id2parents[id] = set()
						id2parents[id].add(parent)
						#print("Adding " + parent + " as parent of " + id)
					else:
						errors.add("WARN parent resource \"" + resource + "\" is not CHEBI") 
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
resource_map["GlyGen"] = "GlyGen" # count = 78622
resource_map["PMID"] = None # count = 78622
resource_map["LINCS"] = "LINCS" # count = 41221
resource_map["CAS"] = "CAS" # count = 31718
resource_map["KEGG"] = "KEGG" # count = 21214
resource_map["Reaxys"] = "Reaxys" # count = 17260
resource_map["Beilstein"] = "Beilstein" # count = 9181
resource_map["MetaCyc"] = None # count = 5876
resource_map["HMDB"] = "HMDB" # count = 5697
resource_map["Wikipedia"] = None # count = 5669
resource_map["KNApSAcK"] = "KNApSAcK" # count = 4623
resource_map["Patent"] = None # count = 4603
resource_map["Drug_Central"] = "Drug_Central" # count = 3742
resource_map["Gmelin"] = "Gmelin" # count = 3456
resource_map["LIPID_MAPS_instance"] = "LIPID_MAPS_instance" # count = 3287
resource_map["PDBeChem"] = "PDBeChem" # count = 2909
resource_map["DrugBank"] = "DrugBank" # count = 2801
resource_map["PPDB"] = "PPDB" # count = 1067
resource_map["Chemspider"] = "Chemspider" # count = 812
resource_map["AGR"] = "AGR" # count = 675
resource_map["UM-BBD_compID"] = "UM-BBD_compID" # count = 618
resource_map["Pesticides"] = "Pesticides" # count = 498
resource_map["MolBase"] = "MolBase" # count = 294
resource_map["VSDB"] = "VSDB" # count = 249
resource_map["Pubchem"] = "PUBCHEM_CID" # count = 173
resource_map["SMID"] = "SMID" # count = 150
resource_map["PDB"] = "PDB" # count = 134
resource_map["WebElements"] = "WebElements" # count = 111
resource_map["CBA"] = "CBA" # count = 110
resource_map["YMDB"] = "YMDB" # count = 102
resource_map["ECMDB"] = "ECMDB" # count = 99
resource_map["COMe"] = "COMe" # count = 90
resource_map["BPDB"] = "BPDB" # count = 90
resource_map["RESID"] = "RESID" # count = 78
resource_map["FooDB"] = "FooDB" # count = 66
resource_map["GlyTouCan"] = "GlyTouCan" # count = 47
resource_map["PMCID"] = None # count = 36
resource_map["LIPID_MAPS_class"] = "LIPID_MAPS_class" # count = 36
resource_map["ChemIDplus"] = "ChemIDplus" # count = 28
resource_map["CTX"] = None # count = 3
resource_map["RO"] = None # count = 1
resource_map["FAO/WHO_standards"] = None # count = 1
resource_map["BFO"] = None # count = 1
resource_map["PPR"] = None # count = 2

if __name__ == '__main__':
    main()
