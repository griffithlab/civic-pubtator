import re

# These are the resources we have patterns for
resources = {"CAS", "CHEBI", "DSSTOX", "MESH", "UNII", "EC"}

accession_pattern2resource = dict()
accession_pattern2resource["[0-9]+-[0-9]+-[0-9]+"] = "CAS"
accession_pattern2resource["[0-9]{1,6}"] = "CHEBI"
accession_pattern2resource["DTXSID[0-9]{7,8,9}"] = "DSSTOX"
# MeSH is D or C followed by either 6 or 9 digits
accession_pattern2resource["(D|C)[0-9]{6}"] = "MESH"
accession_pattern2resource["(D|C)[0-9]{9}"] = "MESH"
# UNII are exactly 10 alphanumeric, uppercase
accession_pattern2resource["[A-Z0-9]{10}"] = "UNII"
# EC numbers start with "EC ", followed by a sequence of numbers, delimited by periods
# The last digit may have be preceded by "n", as in EC 1.1.1.n11, indicating the number is provisional. Note that EC 1.1.1.n11 != EC 1.1.1.11
# Dashes are loosely applied for ranges
# See https://en.wikipedia.org/wiki/Enzyme_Commission_number
accession_pattern2resource["EC [0-9n.-]*"] = "EC"

def guess_resource(accession):
	resources = list()
	for accession_pattern in accession_pattern2resource:
		if re.fullmatch(accession_pattern, accession):
			resources.append(accession_pattern2resource[accession_pattern])
	# First pass is most generic, if it is unique, return it
	if len(resources) < 2:
		return resources
	# Attempt to adjudicate
	if len(resources) == 2 and "MESH" in resources and "UNII" in resources:
		# Identifiers that start with D or C, followed by 9 digits are valid for both MeSH and UNII formats
		# But there are thousands of MESH with this description and only a handful of UNII
		# All these MeSH have the second and third characters as zeros
		# And this is very unlikely to be a real UNII, judging by the randomness of the UNII accession values
		if accession[1:3] == "00":
			resources.remove("UNII")
		else:
			resources.remove("MESH")
	return resources

