import datetime
import re

import entities
import UMLSMultiFileReader

entities_filename="extracted/entities_UMLS.txt.gz"
foldername = "/panfs/pan1.be-md.ncbi.nlm.nih.gov/iret/leamanjr/data/UMLS/2022AB"
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
			cui = "UMLS:" + fields[0]
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
				cui = "UMLS:" + fields[0]
				entity = get_entity(cui)
				types = type_dict[cui]
				entity["types"].update(types)
				str = fields[14]
				entity["names"].add(str)
				
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
resource_map["NCBI"] = "NCBI" # count = 1957848
resource_map["SNOMEDCT_US"] = "SCTID" # count = 1434271
resource_map["MEDCIN"] = "MEDCIN" # count = 901384
resource_map["MSH"] = "MESH" # count = 872027
resource_map["LNC"] = "LNC" # count = 479304
resource_map["ICD10PCS"] = "ICD10PCS" # count = 349906
resource_map["RCD"] = "RCD" # count = 347568
resource_map["NCI"] = "NCI" # count = 337481
resource_map["RXNORM"] = "RXNORM" # count = 318139
resource_map["MTH"] = "MTH" # count = 260978
resource_map["OMIM"] = "OMIM" # count = 183442
resource_map["ICD10CM"] = "ICD10CM" # count = 179063
resource_map["GO"] = "GO" # count = 178923
resource_map["HGNC"] = "HGNC" # count = 173731
resource_map["FMA"] = "FMA" # count = 171017
resource_map["MTHSPL"] = "MTHSPL" # count = 165649
resource_map["SNMI"] = "SNMI" # count = 164179
resource_map["CHV"] = "CHV" # count = 146324
resource_map["NDFRT"] = "NDFRT" # count = 142246
resource_map["NDDF"] = "NDDF" # count = 111468
resource_map["MDR"] = "MDR" # count = 105492
resource_map["UWDA"] = "UWDA" # count = 92913
resource_map["SNOMEDCT_VET"] = "SNOMEDCT_VET" # count = 91666
# MMSL CODEs are not unique (see MMSL:5535, MMSL:11191, MMSL:5304)
resource_map["MMSL"] = None # count = 82144
resource_map["ICPC2ICD10ENG"] = "ICPC2ICD10ENG" # count = 81799
resource_map["MMX"] = "MMX" # count = 72637
resource_map["CPT"] = "CPT" # count = 70920
resource_map["VANDF"] = "VANDF" # count = 62311
resource_map["GS"] = "GS" # count = 61636
resource_map["NCI_CDISC"] = "CDISC" # count = 44483
resource_map["SNM"] = "SNM" # count = 44274
resource_map["ICD9CM"] = "ICD9CM" # count = 40855
resource_map["UMD"] = "UMD" # count = 38728
resource_map["HPO"] = "HP" # count = 30776
resource_map["PDQ"] = "PDQ" # count = 26448
resource_map["ICD10AM"] = "ICD10" # count = 25891
resource_map["MTHICD9"] = "MTHICD9" # count = 23525
resource_map["DRUGBANK"] = "DrugBank" # count = 23180
resource_map["CSP"] = None # count = 22775
resource_map["NCI_FDA"] = "UNII" # count = 22519
resource_map["RCDSY"] = "RCDSY" # count = 22186
resource_map["HCPT"] = "HCPT" # count = 21156
resource_map["AOD"] = "AOD" # count = 20685
resource_map["RCDAE"] = "RCDAE" # count = 17315
resource_map["ICPC2P"] = "ICPC2P" # count = 16897
resource_map["CCPSS"] = "CCPSS" # count = 15840
resource_map["ICD10"] = "ICD10" # count = 13505
resource_map["NIC"] = "NIC" # count = 13495
resource_map["LCH_NW"] = "LCH_NW" # count = 13329
resource_map["HCPCS"] = "HCPCS" # count = 13182
resource_map["NOC"] = "NOC" # count = 12159
resource_map["NEU"] = "NEU" # count = 12159
resource_map["HL7V3.0"] = "HL7V3.0" # count = 12002
resource_map["DXP"] = None # count = 10113
resource_map["ALT"] = "ALT" # count = 9065
resource_map["PSY"] = "PSY" # count = 7961
resource_map["MED-RT"] = "MED-RT" # count = 7843
resource_map["NCI_NICHD"] = "NICHD" # count = 7377
resource_map["NCI_NCI-GLOSS"] = "NCI-GLOSS" # count = 6956
resource_map["ATC"] = "ATC" # count = 6816
resource_map["LCH"] = "LCH" # count = 6652
resource_map["CST"] = "CST" # count = 6444
resource_map["NCI_CTCAE_3"] = "CTCAE_3" # count = 5599
resource_map["HL7V2.5"] = "HL7V2.5" # count = 5019
resource_map["SPN"] = "SPN" # count = 4881
resource_map["NCI_NCI-HGNC"] = "HGNC" # count = 4737
resource_map["NCI_CTCAE_5"] = "CTCAE_5" # count = 4022
resource_map["WHO"] = "WHO" # count = 3831
resource_map["NANDA-I"] = "NANDA-I" # count = 3759
resource_map["USP"] = "USP" # count = 3546
resource_map["COSTAR"] = "COSTAR" # count = 3461
resource_map["MEDLINEPLUS"] = "MEDLINEPLUS" # count = 3379
resource_map["JABL"] = "JABL" # count = 3260
resource_map["CPM"] = "CPM" # count = 3099
resource_map["NCI_CTRP"] = "CTRP" # count = 3013
resource_map["NCI_UCUM"] = "UCUM" # count = 3000
resource_map["ICD10AMAE"] = "ICD10AMAE" # count = 2405
resource_map["PCDS"] = "PCDS" # count = 2229
resource_map["ICNP"] = "ICNP" # count = 2041
resource_map["NCI_DTP"] = "DTP" # count = 1964
resource_map["MTHMST"] = "MTHMST" # count = 1945
resource_map["ICF-CY"] = "ICF-CY" # count = 1771
resource_map["USPMG"] = "USPMG" # count = 1703
resource_map["CCS"] = "CCS" # count = 1617
resource_map["ICF"] = "ICF" # count = 1521
resource_map["HCDT"] = "HCDT" # count = 1410
resource_map["ICPC2EENG"] = "ICPC2EENG" # count = 1379
resource_map["DSM-5"] = "DSM-5" # count = 1337
resource_map["BI"] = "BI" # count = 1251
resource_map["RCDSA"] = "RCDSA" # count = 1185
resource_map["SRC"] = "SRC" # count = 1181
resource_map["NCI_CareLex"] = "CareLex" # count = 1159
resource_map["NCI_BRIDG"] = "BRIDG" # count = 1150
resource_map["ICD10AE"] = "ICD10AE" # count = 1107
resource_map["ICPC"] = "ICPC" # count = 1053
resource_map["NUCCPT"] = "NUCCPT" # count = 959
resource_map["QMR"] = "QMR" # count = 943
resource_map["NCI_CDC"] = "CDC" # count = 923
resource_map["NCI_DCP"] = "DCP" # count = 908
resource_map["CCS_10"] = "CCS_10" # count = 880
resource_map["NCI_CRCH"] = "CRCH" # count = 868
resource_map["NCI_GENC"] = "GENC" # count = 835
resource_map["CDT"] = "CDT" # count = 798
resource_map["NCI_CTCAE"] = "CTCAE" # count = 771
resource_map["NCI_CDISC-GLOSS"] = "CDISC-GLOSS" # count = 718
resource_map["AIR"] = "AIR" # count = 685
resource_map["CVX"] = "CVX" # count = 623
resource_map["OMS"] = "OMS" # count = 554
resource_map["NCI_NCPDP"] = "NCI_NCPDP" # count = 544
resource_map["MTHHH"] = "MTHHH" # count = 527
resource_map["NCI_ICH"] = "ICH" # count = 499
resource_map["AOT"] = "AOT" # count = 471
resource_map["NCI_CTEP-SDC"] = "CTEP-SDC" # count = 462
resource_map["CCC"] = "CCC" # count = 410
resource_map["PPAC"] = "PPAC" # count = 380
resource_map["NCI_BioC"] = "BioC" # count = 336
resource_map["NCI_RENI"] = "RENI" # count = 310
resource_map["NCI_KEGG"] = "KEGG" # count = 277
resource_map["PNDS"] = "PNDS" # count = 262
resource_map["RAM"] = "RAM" # count = 258
resource_map["DDB"] = "DDB" # count = 256
resource_map["NCI_NCI-HL7"] = "NCI-HL7" # count = 244
resource_map["NCI_GAIA"] = "GAIA" # count = 208
resource_map["NCI_PID"] = "PID" # count = 169
resource_map["SOP"] = "SOP" # count = 162
resource_map["NCI_JAX"] = "JAX" # count = 156
resource_map["MTHICPC2ICD10AE"] = "MTHICPC2ICD10AE" # count = 137
resource_map["NCI_DICOM"] = "DICOM" # count = 114
resource_map["ULT"] = None # count = 84
resource_map["MVX"] = None # count = 77
resource_map["MTHICPC2EAE"] = None # count = 53
resource_map["MCM"] = None # count = 43
resource_map["NCI_PI-RADS"] = None # count = 39
resource_map["NCI_ZFin"] = None # count = 25
resource_map["MTHCMSFRF"] = None # count = 8
resource_map["SCTSPA"] = None # count = 1
resource_map["MSHPOL"] = None # count = 1
resource_map["MSHNOR"] = None # count = 1
resource_map["MSHDUT"] = None # count = 1
resource_map["MDRSPA"] = None # count = 1
resource_map["MDRPOR"] = None # count = 1
resource_map["MDRJPN"] = None # count = 1
resource_map["MDRHUN"] = None # count = 1
resource_map["MDRGER"] = None # count = 1
resource_map["MDRFRE"] = None # count = 1
resource_map["MDRDUT"] = None # count = 1
resource_map["MDRCZE"] = None # count = 1

if __name__ == '__main__':
    main()
