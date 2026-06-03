import datetime

import entities

entities_filename="extracted/entities_UNII.txt.gz"
records_filename="downloads/UNII_Records.txt"
names_filename="downloads/UNII_Names.txt"

entities_dict = dict()

def main():
	load_records(records_filename)
	load_names(names_filename)

	print("Loaded " + str(len(entities_dict)) + " entities")
	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict, entities_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def update_record(id, names, xrefs):
	# print("ID = " + id)
	# print("names = " + str(names))
	# print("xrefs = " + str(xrefs))
	# TODO Modify to track what resource suggests what names
	# TODO Modify to track what resource asserts which synonyms 
	entity = None
	if id in entities_dict:
		entity = entities_dict[id]
	else:
		entity = entities.create(id, set(), set(), set(), set())
		entities_dict[id] = entity
	if not names is None:
		entity["names"].update(names)
	if not xrefs is None:
		entity["xrefs"].update(xrefs)

def load_records(filename):
	f = None
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt', encoding='windows-1252') 
	else:
		f = open(filename, 'r', encoding='windows-1252') 
	# Ignore the first line (header)
	next(f)
	for line in f:
		line = line.strip()
		if (len(line) > 0):
			# print(line)
			names = set()
			xrefs = set()
			fields = line.split("\t");
			unii_id = "UNII:" + fields[0].strip()
			pt = fields[1].strip()
			if (len(pt) > 0):
				names.add(pt)
			cas_rn = fields[2].strip()
			if (len(cas_rn) > 0): 
				xrefs.add("CAS:" + cas_rn)
			ec = fields[3].strip()
			if (len(ec) > 0): 
				xrefs.add("EINECS:" + ec)
			ncit = fields[4].strip()
			if (len(ncit) > 0): 
				xrefs.add("NCI:" + ncit)
			rxcui = fields[5].strip()
			if (len(rxcui) > 0): 
				xrefs.add("RXNORM:" + rxcui)
			pubchem = fields[6].strip()
			if (len(pubchem) > 0): 
				xrefs.add("PUBCHEM_CID:" + pubchem)
			itis = fields[7].strip()
			if (len(itis) > 0): 
				xrefs.add("ITIS:" + itis)
			ncbi = fields[8].strip()
			if (len(ncbi) > 0): 
				xrefs.add("NCBITaxon:" + ncbi)
			plants = fields[9].strip()
			if (len(plants) > 0): 
				xrefs.add("PLANTS:" + plants)
			grin = fields[10].strip()
			if (len(grin) > 0): 
				xrefs.add("GRIN:" + grin)
			mpns = fields[11].strip()
			if (len(mpns) > 0): 
				xrefs.add("MPNS:" + mpns)
			inn_id = fields[12].strip()
			if (len(inn_id) > 0): 
				xrefs.add("INN_ID:" + inn_id)
			usan_id = fields[13].strip()
			if (len(usan_id) > 0): 
				xrefs.add("USAN_ID:" + usan_id)
			# TODO Is this how to handle molecular formula?
			mf = fields[14].strip()
			# Suppress "polymer substance not supported"
			if mf.lower() == "polymer substance not supported":
				mf = ""
			if (len(mf) > 0): 
				xrefs.add("MF:" + mf)
			inchikey = fields[15].strip()
			if (len(inchikey) > 0): 
				xrefs.add("INCHIKEY:" + inchikey)
			smiles = fields[16].strip()
			if (len(smiles) > 0): 
				xrefs.add("SMILES:" + smiles)
			# Over 99% of records have ingredient_type = "INGREDIENT SUBSTANCE"
			# so this field is not really useful for categorization
			# ingredient_type = fields[17].strip()
			update_record(unii_id, names, xrefs);
	f.close()

def load_names(filename):
	with open(filename) as f:
		# Ignore the first line (header)
		next(f)
		for line in f:
			line = line.strip()
			if (len(line) > 0):
				# print(line)
				names = set()
				xrefs = set()
				fields = line.split("\t");
				name = fields[0].strip()
				if (len(name) > 0): 
					names.add(name)
				unii_id = "UNII:" + fields[2].strip()
				name = fields[3].strip()
				if (len(name) > 0): 
					names.add(name)
				update_record(unii_id, names, None);

if __name__ == '__main__':
    main()
