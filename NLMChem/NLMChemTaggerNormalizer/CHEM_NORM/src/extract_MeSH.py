import codecs
import datetime
import re
import sys

import entities
import chemicals

entities_dict = dict()
heading2id = dict()
tree2id = dict()

def main():
	if len(sys.argv) != 4:
		print("Usage: " + sys.argv[0] + " <dfilename> <cfilename> <entities_filename>")
		sys.exit()

	dfilename = sys.argv[1]
	cfilename = sys.argv[2]
	entities_filename = sys.argv[3]

	load(dfilename)
	print("Loaded " + str(len(entities_dict)) + " entities")

	load(cfilename)
	print("Loaded " + str(len(entities_dict)) + " entities")

	print("Identifying parents from trees and headings")
	for id, entity in entities_dict.items():
		parents = set()
		for parent_tree in entity["parent_trees"]:
			parents.add(tree2id[parent_tree])
		del entity["parent_trees"]
		for parent_heading in entity["parent_headings"]:
			parents.add(heading2id[parent_heading])
		del entity["parent_headings"]
		entity["parents"] = parents
	
	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict, entities_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def load(filename):
	print("Loading entities from " + filename)
	with codecs.open(filename, 'r', encoding="utf8") as f:
		id, heading, types, names, trees, parent_headings, xrefs = reset()
		for line in f:
			# print(line)
			line = line.strip()
			if line == "*NEWRECORD":
				# Output record if we have any data
				create(id, heading, types, names, trees, parent_headings, xrefs)
				# print("New record")
				id, heading, types, names, trees, parent_headings, xrefs = reset()
			elif line.startswith("MN = "):
				tree = line[5:]
				# print("Found tree \"" + value + "\"")
				trees.add(tree)
			elif line.startswith("MH = "):
				heading = line[5:]
				# print("Found heading name \"" + heading + "\"")
				names.add(heading)
			elif line.startswith("HM = "):
				parent_heading = line[5:]
				# print("Found parent heading \"" + parent_heading + "\"")
				# Strip preceding asterisk
				if parent_heading.startswith("*"):
					parent_heading = parent_heading[1:]
				# Strip "/asdf" suffix
				index = parent_heading.find("/")
				if index >= 0:
					parent_heading = parent_heading[:index]
				parent_headings.add(parent_heading)
			elif line.startswith("ST = "):
				value = line[5:]
				# print("Found semantic type \"" + value + "\"")
				types.add("UMLS:" + value)
			elif line.startswith("PA = "):
				# TODO Add these as a typed relationship
				value = line[5:]
				# print("Found pharmaceutical action \"" + value + "\"")
			elif line.startswith("NM = "):
				value = line[5:]
				# print("Found name \"" + value + "\"")
				names.add(value)
			elif line.startswith("ENTRY = "):
				# TODO Add semantic type, name type (LAB, NON, etc) and equivalency (EQV, NRW) from remaining fields
				value = line[8:]
				fields = value.split("|");
				# print("Found entry name \"" + fields[0] + "\"")
				names.add(fields[0])
			elif line.startswith("PRINT ENTRY = "):
				# TODO Add semantic type, name type (LAB, NON, etc) and equivalency (EQV, NRW) from remaining fields
				value = line[14:]
				fields = value.split("|");
				# print("Found print entry name \"" + fields[0] + "\"")
				names.add(fields[0])
			elif line.startswith("SY = "):
				# TODO Add semantic type, name type (LAB, NON, etc) and equivalency (EQV, NRW) from remaining fields
				value = line[5:]
				fields = value.split("|");
				# print("Found entry name \"" + fields[0] + "\"")
				names.add(fields[0])
			elif line.startswith("N1 = "):
				value = line[5:]
				# print("Found formula name \"" + value + "\"")
				names.add(value)
			elif line.startswith("RR = ") or line.startswith("RN = "):
				# Normalize case in EC accessions and protect the space
				line = re.sub("= [Ee][Cc] ", "= EC_", line)
				value = line[5:]
				# Normalize whitespace in front of any parens
				value = re.sub("\s*\(", " (", value)
				fields = value.split(" ");
				if fields[0] != "0":
					xref_text = fields[0].replace("EC_", "EC ")
					# print("Found record identifier \"" + xref_text + "\"")
					if xref_text.startswith("txid"):
						xref_resources = ["NCBITaxon"]
						xref_text = xref_text[4:]
					else:
						xref_resources = chemicals.guess_resource(xref_text)
						if xref_text.startswith("EC "):
							xref_text = xref_text[3:]
					if len(xref_resources) == 1:
						xrefs.add(xref_resources[0] + ":" + xref_text)
					else:
						print("WARN: could not guess resource for xref: \"" + xref_text + "\", guesses: " + str(xref_resources))
			elif line.startswith("UI = "):
				id = "MESH:" + line[5:]
				# print("Found id \"" + id + "\"")
		create(id, heading, types, names, trees, parent_headings, xrefs)

# Other fields, by count
# 277178 RECTYPE = record type, either "D" or "C"
# 277178 DA = ? date
# 266631 NM_TH = source abbreviation & year
# 247803 FR = ? numeric value in range [1, 1000]
# 246630 SO = citation
# 209555 NO = notes on definition for supplemental concepts, sometimes has an XRef
# 198429 MR = ? date
#  77079 PI = ? previous name
#  44865 II
#  35637 MH_TH = source abbreviation & year
#  29351 DX = ? date
#  29351 DC = ? numeric value in range [1, 4]
#  29159 MS = Scope note; sometimes includes definitions or citations
#  28224 AQ = List of allowed qualifiers
#  25320 HN = ? previous
#  24889 PM = ? previous
#  12491 AN = Notes on definition and qualifiers
#   8793 FX = Headings listed as "see also" on the website, related in some way but not synonymous
#   6868 CATSH = ?
#   4126 DE = "Entry version", seems to be an all caps version of the name, with ad-hoc abbreviations
#   3005 OL = ? notes
#   1571 DS
#    974 EC
#    116 RH = Tree root name
#     66 CX

def reset():
	return "", "", set(), set(), set(), set(), set()

def create(id, heading, types, names, trees, parent_headings, xrefs):
	if len(id) == 0:
		return
	entity = entities.create(id, types, names, set(), xrefs)
	entity["parent_trees"] = get_parent_trees(trees)
	entity["parent_headings"] = parent_headings
	entities_dict[id] = entity
	for tree in trees:
		if tree in tree2id:
			if tree2id[tree] != id:
				print("WARN tree \"" + tree + "\" already defined as ID " + tree2id[tree])
		tree2id[tree] = id
	if len(heading) > 0:
		accession = id.split(":")[1]
		heading2id["{} - {}".format(accession, heading)] = id

def get_parent_trees(trees):
	parent_trees = set()
	for tree in trees:
		index = tree.rfind(".")
		if index >= 0:
			parent_trees.add(tree[:index])
	return parent_trees

if __name__ == '__main__':
    main()
