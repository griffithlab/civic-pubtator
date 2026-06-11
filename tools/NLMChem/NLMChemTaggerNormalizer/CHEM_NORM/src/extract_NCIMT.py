import datetime
import re

import entities
import UMLSMultiFileReader

entities_filename="extracted/entities_NCIMT.txt.gz"
foldername = "/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/NCIMetathesaurus/META/"
filename_MRSTY="MRSTY.RRF"
# NOTE each file is broken at exactly 2^30 characters
filename_MRCONSO="MRCONSO.RRF"
allowed_LAT = {"ENG"} # Language

type_dict = dict()
entities_dict = dict()

# TODO Add definitions
# TODO Add hierarchies
# TODO Add related concepts
# TODO Add types

def main():
	print("Loading MRSTY file")
	start = datetime.datetime.now()
	load_MRSTY(foldername, filename_MRSTY)
	print("Elapsed = " + str(datetime.datetime.now() - start))

	print("Loading MRCONSO file")
	start = datetime.datetime.now()
	load_MRCONSO(foldername, filename_MRCONSO)
	print("Elapsed = " + str(datetime.datetime.now() - start))

	print("Loaded " + str(len(entities_dict)) + " entities")
	print("Writing out dictionary")
	start = datetime.datetime.now()
	entities.write(entities_dict, entities_filename)
	print("Elapsed = " + str(datetime.datetime.now() - start))
	print("Done.")

def get_entity(id):
	entity = None
	if id in entities_dict:
		entity = entities_dict[id]
	else:
		entity = entities.create(id, set(), set(), set(), set())
		entities_dict[id] = entity
	return entity

# Format for MRSTY.RRF:
# 0 CUI|Unique identifier for concept
# 1 TUI|Unique identifier of semantic type
def load_MRSTY(foldername, filename):
	f = UMLSMultiFileReader.open(foldername, filename)
	for line in f:
		line = line.strip()
		if len(line) > 0:
			#print(line)
			fields = line.split("|")
			cui = "NCIMT:" + fields[0]
			tui = "UMLS:" + fields[1]
			if not cui in type_dict:
				type_dict[cui] = set()
			type_dict[cui].add(tui)

# Format for MRCONSO.RRF:
# 0 CUI|Unique identifier for concept||8|8.00|8|MRCONSO.RRF|char(8)|
# 1 LAT|Language of Term(s)||3|3.00|3|MRCONSO.RRF|char(3)|
# 2 TS|Term status||1|1.00|1|MRCONSO.RRF|char(1)|
# 3 LUI|Unique identifier for term||8|8.14|9|MRCONSO.RRF|varchar(10)|
# 4 STT|String type||2|2.01|3|MRCONSO.RRF|varchar(3)|
# 5 SUI|Unique identifier for string||8|8.34|9|MRCONSO.RRF|varchar(10)|
# 6 ISPREF|Indicates whether AUI is preferred||1|1.00|1|MRCONSO.RRF|char(1)|
# 7 AUI|Unique identifier for atom||8|8.66|9|MRCONSO.RRF|varchar(9)|
# 8 SAUI|Source asserted atom identifier||0|2.37|18|MRCONSO.RRF|varchar(50)|
# 9 SCUI|Source asserted concept identifier||0|5.35|50|MRCONSO.RRF|varchar(50)|
# 10 SDUI|Source asserted descriptor identifier||0|2.08|13|MRCONSO.RRF|varchar(50)|
# 11 SAB|Source abbreviation||2|5.63|15|MRCONSO.RRF|varchar(40)|
# 12 TTY|Term type in source||2|2.33|11|MRCONSO.RRF|varchar(20)|
# 13 CODE|Unique Identifier or code for string in source||1|7.29|63|MRCONSO.RRF|varchar(100)|
# 14 STR|String||1|36.95|2916|MRCONSO.RRF|varchar(3000)|
# 15 SRL|Source Restriction Level||1|1.00|1|MRCONSO.RRF|integer|
# 16 SUPPRESS|Suppressible flag||1|1.00|1|MRCONSO.RRF|char(1)|
# 17 CVF|Content view flag||0|1.05|5|MRCONSO.RRF|varchar(50)|
def load_MRCONSO(foldername, filename):
	errors = set()
	f = UMLSMultiFileReader.open(foldername, filename)
	for line in f:
		line = line.strip()
		if len(line) > 0:
			#print(line)
			fields = line.split("|")
			lat = fields[1]
			if lat in allowed_LAT:
				tty = fields[12]
				code = fields[13]
				sab, err = map_sab(fields[11], code, tty)
				if not err:
					errors.add(err) 
				
				# Get entity for CUI, add types & names
				cui = "NCIMT:" + fields[0]
				entity = get_entity(cui)
				types = type_dict[cui]
				entity["types"].update(types)
				str = fields[14]
				entity["names"].add(str)
				if not cui.startswith("NCIMT:CL"):
					# Add an automatic xref to the UMLS CUI
					entity["xrefs"].add("UMLS:" + fields[0])

				if sab:
					# syn_id is the secondary ID
					syn_id = code
					if not syn_id.startswith(sab + ":"):
						syn_id = sab + ":" + code
					syn_entity = get_entity(syn_id)
					syn_entity["types"].update(types)
					syn_entity["names"].add(str)
					syn_entity["xrefs"].add(cui)
					entity["xrefs"].add(syn_id)
					# TODO Look at names between syn_id and cui to determine what kind of synonymy it is
					# TODO Consider synonymies between all syn_ids

	for error in errors:
		print(error)

# Returns sab, code, error
def map_sab(sab, code, tty):
	errors = set()
	# Map resource with dictionary
	if sab in resource_map:
		sab = resource_map[sab]
	else:
		return (None, "WARN SAB \"" + sab + "\" is unknown")
	# Resource "MTHSPL" is usually either UNII or PROD_NDC (product NDC)
	if sab == "MTHSPL":
		if re.fullmatch("[A-Z0-9]{10}", code):
			sab = "UNII"
		if re.fullmatch("[0-9]{5}-[0-9]{4}", code) or re.fullmatch("[0-9]{5}-[0-9]{3}", code) or re.fullmatch("[0-9]{4}-[0-9]{4}", code):
			sab = "PROD_NDC" #
		else:
			# There are usually a few of these
			return (None, "WARN SAB \"" + sab + "\" code does not match UNII or PROD_NDC")
	# Check the codes
	if sab == "MESH" and code.startswith("Q"):
		# These are qualifiers
		return (None, None)
	if sab == "UNII" and not re.fullmatch("[A-Z0-9]{10}", code):
		# These are not standard UNII and are frequent spurious synonyms
		return (None, None)
	if code == "NOCODE":
		return (None, None)
	if code.startswith("MTHU"):
		# These ids are created during Metathesaurus processing and frequently do not properly reflect synonyms
		return (None, None)
	if (sab == "NCI" or sab == "CDISC") and not re.fullmatch("C[0-9]+", code):
		# These are not standard accession ID and are frequent spurious synonyms
		return (None, None)
	if sab == "OMIM":
		# OMIM cross references gene names and phenotypes under the same code as the disease name
		if tty == "PT" or tty == "ETAL" or tty == "ACR" or tty == "ET":
			return (None, None)
	return (sab, None)
	
resource_map = dict()
resource_map["NCBI"] = "NCBI" # count = 1422261
resource_map["SNOMEDCT_US"] = "SCTID" # count = 864817
resource_map["MSH"] = "MESH" # count = 838027
resource_map["LNC"] = "LNC" # count = 363369
resource_map["ICD10PCS"] = "ICD10PCS" # count = 323920
resource_map["RXNORM"] = "RXNORM" # count = 305697
resource_map["NCI"] = "NCI" # count = 295657
resource_map["ICD10CM"] = "ICD10CM" # count = 173321
resource_map["HGNC"] = "HGNC" # count = 164908
resource_map["MTH"] = "MTH" # count = 158750
resource_map["OMIM"] = "OMIM" # count = 158136
resource_map["GO"] = "GO" # count = 153823
resource_map["FMA"] = "FMA" # count = 139095
resource_map["NDFRT"] = "NDFRT" # count = 137207
resource_map["MTHSPL"] = "MTHSPL" # count = 136491
resource_map["MDR"] = "MDR" # count = 102243
resource_map["UWDA"] = "UWDA" # count = 92913
resource_map["RADLEX"] = "RADLEX" # count = 63045 # TODO Check
resource_map["VANDF"] = "VANDF" # count = 57464
resource_map["PDQ"] = "PDQ" # count = 43667
resource_map["ICD9CM"] = "ICD9CM" # count = 40855
resource_map["UMD"] = "UMD" # count = 35746
resource_map["CDISC"] = "CDISC" # count = 33573
resource_map["GARD"] = "GARD" # count = 25241
resource_map["MTHICD9"] = "MTHICD9" # count = 23525
resource_map["CSP"] = None # count = 22775
resource_map["FDA"] = "UNII" # count = 22508
resource_map["CBO"] = "CBO" # count = 20906 # TODO Check
resource_map["AOD"] = "AOD" # count = 20685
resource_map["ICD10"] = "ICD10" # count = 19555
resource_map["HPO"] = "HP" # count = 19491
resource_map["HL7V3.0"] = "HL7V3.0" # count = 12995
resource_map["HCPCS"] = "HCPCS" # count = 12560
resource_map["ISO3166-2"] = "ISO3166-2" # count = 10963 # TODO Check
resource_map["DXP"] = None # count = 10113
resource_map["NCI-GLOSS"] = "NCI-GLOSS" # count = 6958
resource_map["NICHD"] = "NICHD" # count = 6948
resource_map["CST"] = "CST" # count = 6444
resource_map["CTCAE"] = "CTCAE" # count = 6366
resource_map["SPN"] = "SPN" # count = 4881
resource_map["NCI-HGNC"] = "HGNC" # count = 4457
resource_map["ICDO"] = "ICDO" # count = 3851
resource_map["NCIMTH"] = "NCIMTH" # count = 3755 # TODO Check
resource_map["COSTAR"] = "COSTAR" # count = 3461
resource_map["MEDLINEPLUS"] = "MEDLINEPLUS" # count = 3232
resource_map["UCUM"] = "UCUM" # count = 2922
resource_map["NPO"] = "NPO" # count = 2543 # TODO Check
resource_map["PMA"] = "PMA" # count = 2082 # TODO Check
resource_map["DTP"] = "DTP" # count = 1964
resource_map["MTHMST"] = "MTHMST" # count = 1945
resource_map["USPMG"] = "USPMG" # count = 1608
resource_map["CARELEX"] = "CareLex" # count = 1159
resource_map["BRIDG"] = "BRIDG" # count = 1150
resource_map["GENC"] = "GENC" # count = 1115
resource_map["ICPC"] = "ICPC" # count = 1053
resource_map["MGED"] = "MGED" # count = 965 # TODO Check
resource_map["QMR"] = "QMR" # count = 943
resource_map["CDC"] = "CDC" # count = 923
resource_map["DCP"] = "DCP" # count = 908
resource_map["CCS_10"] = "CCS_10" # count = 878
resource_map["CRCH"] = "CRCH" # count = 868
resource_map["NCPDP"] = "NCPDP" # count = 544
resource_map["ICH"] = "ICH" # count = 500
resource_map["SRC"] = "SRC" # count = 486
resource_map["AOT"] = "AOT" # count = 471
resource_map["CTEP-SDC"] = "CTEP-SDC" # count = 462
resource_map["MTHHH"] = "MTHHH" # count = 426
resource_map["CTEP"] = "CTEP" # count = 373 # TODO Check
resource_map["MDBCAC"] = "MDBCAC" # count = 342 # TODO Check
resource_map["CVX"] = "CVX" # count = 340
resource_map["BioC"] = "BioC" # count = 336
resource_map["RENI"] = "RENI" # count = 310
resource_map["KEGG"] = "KEGG" # count = 276
resource_map["NCI-HL7"] = "NCI-HL7" # count = 244
resource_map["GAIA"] = "GAIA" # count = 208
resource_map["PNDS"] = "PNDS" # count = 199 # TODO Check
resource_map["PID"] = "PID" # count = 169
resource_map["JAX"] = "JAX" # count = 156
resource_map["SOP"] = "SOP" # count = 145
resource_map["DICOM"] = "DICOM" # count = 114
resource_map["MVX"] = None # count = 69
resource_map["MCM"] = None # count = 43
resource_map["PI-RADS"] = None # count = 39
resource_map["ZFIN"] = None # count = 25
resource_map["MTHCMSFRF"] = None # count = 8





if __name__ == '__main__':
    main()
