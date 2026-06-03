import collections
import re
import sys

def main():
	if len(sys.argv) != 4:
		print("Usage: " + sys.argv[0] + " <d_filename> <c_filename> <chemicals_filename>")
		sys.exit()

	d_filename = sys.argv[1]
	c_filename = sys.argv[2]
	chemicals_filename = sys.argv[3]

	id2concept = dict()
	load(d_filename, id2concept)
	print("Loaded " + str(len(id2concept)) + " concepts")
	load(c_filename, id2concept)
	print("Loaded " + str(len(id2concept)) + " concepts")
	
	with open(chemicals_filename, "w") as chemicals_file:
		for id, concept in id2concept.items():
			if id == "MESH:C000604172" or id == "MESH:D005456" or id == "MESH:D000067029" or id == "MESH:C025476":
				print(str(concept))
			is_chemical = decide_if_chemical(concept)
			chemicals_file.write("{}\t{}\n".format(id, str(is_chemical).lower()))
	print("Done.")

def load(filename, id2concept):
	print("Loading concepts from " + filename)
	with open(filename, "r") as f:
		id = None
		trees = set()
		for line in f:
			# print(line)
			line = line.strip()
			if line == "*NEWRECORD":
				# Output record if we have any data
				create_concept(id, trees, id2concept)
				id = None
				trees = set()
				continue
			if line.startswith("MN = "):
				tree = line[5:]
				# print("Found tree \"" + tree + "\"")
				trees.add(tree)
				continue
			if line.startswith("HM = "):
				parent_heading = line[5:]
				#print("Found parent heading \"" + parent_heading + "\"")
				# Strip preceding asterisk
				if parent_heading.startswith("*"):
					parent_heading = parent_heading[1:]
				# Strip any qualifiers
				index = parent_heading.find("/")
				if index >= 0:
					parent_heading = parent_heading[:index]
				# Parse "ID - Heading" format
				index = parent_heading.find(" - ")
				if index < 0:
					raise ValueError()
				parent_id = "MESH:" + parent_heading[:index]
				parent_trees = id2concept[parent_id]["trees"]
				#print("parent_id \"" + parent_id + "\"")
				#print("parent_trees \"" + str(parent_trees) + "\"")
				trees.update(parent_trees)
				continue
			if line.startswith("UI = "):
				id = "MESH:" + line[5:]
				# print("Found id \"" + id + "\"")
				continue
		create_concept(id, trees, id2concept)

def create_concept(id, trees, id2concept):
	#print("Creating {}: {}".format(id, trees))
	if id is None:
		return
	if not id in id2concept:
		id2concept[id] = dict()
		id2concept[id]["trees"] = set()
	id2concept[id]["trees"].update(trees)
	
def decide_if_chemical(concept):
	trees = concept.get("trees")
	if trees is None:
		return False
	default_output = False
	protein_override = False
	antibody_override = False
	for tree in trees:
		if re.match("D01(\\.[0-9]+)*", tree):
			# Inorganic chemicals
			default_output = True
		elif re.match("D02(\\.[0-9]+)*", tree):
			# Organic chemicals
			default_output = True
		elif re.match("D03(\\.[0-9]+)*", tree):
			# Heterocyclic compounds
			default_output = True
		elif re.match("D04(\\.[0-9]+)*", tree):
			# Polycyclic compounds
			default_output = True
		elif re.match("D05\\.750(\\.[0-9]+)*", tree):
			# Polymers
			default_output = True
		elif re.match("D09(\\.[0-9]+)*", tree):
			# Carbohydrates
			default_output = True
		elif re.match("D10(\\.[0-9]+)*", tree):
			# Lipids
			default_output = True
		elif re.match("D12\\.125(\\.[0-9]+)*", tree):
			# Amino acids
			default_output = True
		elif re.match("D12\\.644(\\.[0-9]+)*", tree):
			# Peptides
			default_output = True
		elif re.match("D12\\.776(\\.[0-9]+)*", tree):
			# Proteins
			protein_override = True
			if re.match("D12\\.776\\.124\\.486\\.485\\.114\\.224(\\.[0-9]+)*", tree) or re.match("D12\\.776\\.124\\.790\\.651\\.114\\.224(\\.[0-9]+)*", tree) or re.match("D12\\.776\\.377\\.715\\.548\\.114\\.224(\\.[0-9]+)*", tree):
				# Monoclonal Antibodies
				antibody_override = True
			elif re.match("D12\\.776\\.124\\.486\\.485\\.114\\.125(\\.[0-9]+)*", tree) or re.match("D12\\.776\\.124\\.790\\.651\\.114\\.134(\\.[0-9]+)*", tree) or re.match("D12\\.776\\.377\\.715\\.548\\.114\\.134(\\.[0-9]+)*", tree):
				# Bispecific Antibodies
				antibody_override = True
		elif re.match("D13\\.570(\\.[0-9]+)*", tree):
			# Nucleosides
			default_output = True
		elif re.match("D13\\.695(\\.[0-9]+)*", tree):
			# Nucleotides
			default_output = True
	if (default_output and not protein_override) or antibody_override:
		return True
	return False

if __name__ == '__main__':
    main()
