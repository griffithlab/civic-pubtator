import codecs
import datetime
import gzip

import entities

entities_filename="extracted/entities_DSSTox.txt.gz"
cas_filename="/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/DSSTox/2021/DSSTox_Identifiers_and_CASRN_2021r1_MOD.csv.gz"
pubchem_filename="/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/DSSTox/2021/PubChem_DTXSID_mapping_file.txt.gz"
inchi_filename="/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/DSSTox/2021/dsstox_20160701.tsv.gz"
synonym_filename="/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/DSSTox/2021/DSSTox_Synonyms_20180315.sdf.gz"

entities_dict = dict()

def main():
	print("Loading CAS file")
	load_cas_file(cas_filename)
	print("Loading INCHI file")
	load_inchi_file(inchi_filename)
	print("Loading PubChem file")
	load_pubchem_file(pubchem_filename)
	print("Loading Synonym SDF file")
	load_synonym_file(synonym_filename)

	print("Loaded " + str(len(entities_dict)) + " entities")
	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict, entities_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def update_record(id, names, xrefs):
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

def parse_CSV(line):
	# Parses a csv line with fully-quoted values
	values = list()
	index = 0
	while index < len(line):
		# Get whitespace
		while index < len(line) and line[index].isspace():
			index += 1
		if len(values) > 0:
			# Get a comma
			if index >= len(line) or line[index] != ",":
				char = line[index] if index < len(line) else "<EOL>"
				raise ValueError("Unable to parse CSV line at character {} ({}), expected comma: \"{}\"".format(index, char, line))
			index += 1
		# Get whitespace
		while index < len(line) and line[index].isspace():
			index += 1
		# Check if EOL or another comma
		if index >= len(line) or line[index] == ",":
			values.append("")
			continue # Do not advance past the comma
		# Get double quote
		if line[index] != "\"":
			char = line[index] if index < len(line) else "<EOL>"
			raise ValueError("Unable to parse CSV line at character {} ({}), expected quotes: \"{}\"".format(index, char, line))
		index += 1
		# Get a value
		start = index
		done = False
		while not done:
			while index < len(line) and line[index] != "\"":
				index += 1
			if index + 1 < len(line) and line[index + 1] == "\"":
				index += 2
			else:
				done = True
		# Get double quote
		if index >= len(line) or line[index] != "\"":
			char = line[index] if index < len(line) else "<EOL>"
			raise ValueError("Unable to parse CSV line at character {} ({}), expected quotes: \"{}\"".format(index, char, line))
		values.append(line[start:index].replace("\"\"", "\""))
		index += 1
	return values

def load_cas_file(filename):
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt', encoding="latin-1") 
	else:
		f = codecs.open(filename, 'r', encoding="latin-1") 
	# Ignore the first line (header)
	next(f)
	for line in f:
		line = line.strip()
		if len(line) > 0:
			fields = parse_CSV(line)
			if len(fields) != 6:
				raise ValueError("Expected 6 fields (dtxsid, dtxcid, casrn, preferredName, inchi, inchiKey), got {}: {}".format(len(fields), fields))
			id = "DSSTOX:" + fields[0]
			xrefs = set()
			if len(fields[2]) > 0:
				if not fields[2].startswith("NOCAS_"):
					xrefs.add("CAS:" + fields[2])
			if len(fields[4]) > 0:
				xrefs.add("INCHI:" + fields[4])
			if len(fields[5]) > 0:
				xrefs.add("INCHIKEY:" + fields[5])
			names = set()
			if len(fields[3]) > 0:
				name = fields[3]
				# Remove " (non-preferred name)" at end of terms
				if name.endswith("(non-preferred name)"):
					name = name[0:len(name)-20].strip()
				names.add(name)
			#print("Adding id=" + id + " names = " + str(names) + " xrefs = " + str(xrefs))
			update_record(id, names, xrefs)
	f.close()
		
def load_cas_file_OLD(filename):
	f = None
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt', encoding="latin-1") 
	else:
		f = codecs.open(filename, 'r', encoding="latin-1") 
	# Ignore the first line (header)
	next(f)
	for line in f:
		line = line.strip()
		if len(line) > 0:
			#print(line)
			fields = line.split("\t")
			id = "DSSTOX:" + fields[1]
			xrefs = set()
			if len(fields[0]) > 0:
				if not fields[0].startswith("NOCAS_"):
					xrefs.add("CAS:" + fields[0])
			names = set()
			if len(fields[2]) > 0:
				name = fields[2]
				# Remove surrounding double quotes, if any
				if name.startswith("\"") and name.endswith("\""):
					name = name[1:len(name)-1]
				# Remove " (non-preferred name)" at end of terms
				if name.endswith("(non-preferred name)"):
					name = name[0:len(name)-20].strip()
				names.add(name)
			#print("Adding id=" + id + " names = " + str(names) + " xrefs = " + str(xrefs))
			update_record(id, names, xrefs)
	f.close()

def load_inchi_file(filename):
	f = None
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt') 
	else:
		f = open(filename, 'r') 
	for line in f:
		line = line.strip()
		if len(line) > 0:
			# print(line)
			fields = line.split("\t")
			id = "DSSTOX:" + fields[0]
			xrefs = set()
			if len(fields) > 1 and len(fields[1]) > 0:
				xrefs.add("INCHI:" + fields[1])
			if len(fields) > 2 and len(fields[2]) > 0:
				xrefs.add("INCHIKEY:" + fields[2])
			update_record(id, set(), xrefs)
	f.close()

def load_pubchem_file(filename):
	f = None
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt') 
	else:
		f = open(filename, 'r') 
	# Ignore the first line (header)
	next(f)
	for line in f:
		line = line.strip()
		if len(line) > 0:
			# print(line)
			fields = line.split("\t")
			sid = fields[0].strip()
			cid = fields[1].strip()
			if cid == "DSSTox":
				# "DSSTox" as the CID appears to be a placeholder
				cid = ""
			accession = fields[2].strip()
			# Ignore dummy DSSTOX accessions (a 5 digit serial number)
			if accession.startswith("DTXSID"):
				xrefs = set()
				if len(sid) > 0:
					xrefs.add("PUBCHEM_SID:" + sid)
				if len(cid) > 0:
					xrefs.add("PUBCHEM_CID:" + cid)
				update_record("DSSTOX:" + accession, set(), xrefs)
	f.close()

def load_synonym_file(filename):
	f = None
	if filename.endswith(".gz"):
		f = gzip.open(filename, 'rt', encoding="utf-8") 
	else:
		f = codecs.open(filename, 'r', encoding="utf-8") 
	state = 0 # Ignore
	id = None
	names = list()
	xrefs = set()
	processing_added = 0
	processing_removed = 0
	for line in f:
		line = line.strip()
		if len(line) > 0:
			#print("line = \"{}\" state = {}, id = {}, names = {}, xrefs = {}".format(line, state, id, names, xrefs))
			if line == ">  <DSSTox_Structure_Id>":
				state = 0 # Ignore
			elif line == ">  <QC_Level>":
				state = 0 # Ignore
			elif line == ">  <Dashboard_URL>":
				state = 0 # Ignore
			elif line == ">  <DSSTox_Substance_id>":
				state = 1 # ID
			elif line == ">  <Preferred_Name>":
				state = 2 # Name OR XRef
			elif line == ">  <CAS-RN>":
				state = 3 # CAS XRef
			elif line == ">  <Alternate_CAS-RN>":
				state = 3 # CAS XRef
			elif line == ">  <Deleted_CAS-RN>":
				state = 3 # CAS XRef
			elif line == ">  <Synonyms>":
				state = 2 # Name OR XRef
			elif line.startswith(">  "):
				print("WARN Unknown section header: \"" + line + "\"")
				state = 0 # Ignore
			elif line == "$$$$":
				#print("Adding id=" + id + " names = " + str(names) + " xrefs = " + str(xrefs))
				if id is None:
					raise ValueError("Cannot complete record, id is None: id = {}, names = {}, xrefs = {}".format(id, names, xrefs))
				name_set = set(names)
				name_set_processed = process_names(id, names)
				processing_added = processing_added + len(name_set_processed - name_set)
				processing_removed = processing_removed + len(name_set - name_set_processed)
				#if not name_set == name_set_processed: 
				#	print("Name sets do not match: ")
				#	print("\t  added: " + str(name_set_processed - name_set))
				#	print("\tremoved: " + str(name_set - name_set_processed))
				update_record(id, name_set_processed, xrefs)
				state = 0 # Ignore
				id = None
				names = list()
				xrefs = set()
			elif state == 1:
				# ID
				id = "DSSTOX:" + line
			elif state == 2:
				# Name OR XRef
				if line.startswith("UNII-"):
					xrefs.add("UNII:" + line[5:])
				elif line.startswith("AGN-"):
					xrefs.add("AGN:" + line[4:])
				#elif line.startswith("NCI-"): # These look like NCI identifiers but do not match
				#	xrefs.add("NCI:" + line[4:])
				elif line.startswith("EINECS "):
					xrefs.add("EINECS:" + line[7:])
				elif line.startswith("BRN "):
					xrefs.add("BRN:" + line[4:])
				elif line.startswith("NSC "):
					xrefs.add("NSC:" + line[4:])
				elif line.startswith("EPA "):
					xrefs.add("EPA:" + line[4:])
				elif line.startswith("BAS "):
					xrefs.add("BAS:" + line[4:])
				elif line.startswith("FEMA "):
					xrefs.add("FEMA:" + line[5:])
				elif line.startswith("RCRA "):
					xrefs.add("RCRA:" + line[5:])
				elif line.startswith("USAF "):
					xrefs.add("USAF:" + line[5:])
				elif line.startswith("Caswell "):
					xrefs.add("Caswell:" + line[8:])
				else:
					names.append(line)
					#fields = line.replace("-", " ").split(" ")
					#print("FIELD\t" + fields[0])
			elif state == 3:
				# CAS XRef
				xrefs.add("CAS:" + line)
			elif state != 0:
				print("WARN Unknown state: \"" + str(state) + "\"")
				state = 0 # Ignore
	f.close()
	print("Name processing added " + str(processing_added) + " names")
	print("Name processing removed " + str(processing_removed) + " names")

def process_names(id, name_list):
	# Identify if the concatenation of any two names matches another name
	# Prepare set of processed names
	processed_set = set()
	for name in name_list:
		processed_set.add(name.lower())
	# Check all pairs to see if present
	handled = set()
	name_set = set()
	for i in range(0, len(name_list)-1):
		name_i = name_list[i]
		name_i1 = name_list[i+1]
		name = name_i + name_i1
		name_processed = name.lower()
		if name_processed in processed_set:
			#print("WARN names \"" + name_i + "\" and \"" + name_i1 + "\" matches another name: \"" + name_processed + "\" + for concept \"" + id)
			handled.add(i)
			handled.add(i + 1)
			name_set.add(name)
	# Add names not yet handled
	for i in range(0, len(name_list)):
		if not i in handled:
			name_set.add(name_list[i])
	return name_set

# Even after process_names, there are still many names that appear as synonyms in 6 or more DSSTox records in the synonyms file
# T, N, P, d, e, l, a, ne, ol, de, id, te, ate, cid, me), PCB, acid, c acid, ic acid, Benzoate, brassinosteroids, 3-Oxa-9-azatricyclo[3.3.1.02,4]nonane, benzeneacetic acid deriv.

if __name__ == '__main__':
    main()
