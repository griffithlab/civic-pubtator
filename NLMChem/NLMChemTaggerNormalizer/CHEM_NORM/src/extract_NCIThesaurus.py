import codecs
import datetime
import re
import sys

import entities
import chemicals

entities_dict = dict()

def main():
	if len(sys.argv) != 3:
		print("Usage: " + sys.argv[0] + " <input_filename> <entities_filename>")
		sys.exit()

	input_filename = sys.argv[1]
	entities_filename = sys.argv[2]

	load(input_filename)
	print("Loaded " + str(len(entities_dict)) + " entities")

	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict, entities_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def load(filename):
	print("Loading entities from " + filename)
	with codecs.open(filename, 'r', encoding="utf8") as f:
		for line in f:
			#print(line)
			line = line.strip()
			if len(line) == 0:
				continue
			fields = line.split("\t")
			if len(fields) < 8:
				print("Line: " + line)
				print("len(fields): " + str(len(fields)))
				print("fields: " + str(fields))
				continue
			id = "NCI:" + fields[0]
			# fields[1] is an OWL ID
			parents = ["NCI:" + parent_id for parent_id in fields[2].split("|")]
			names = [fields[5]] # Official name
			names.extend(fields[3].split("|"))
			# fields[4] is a definition
			# fields[6] is status
			# TODO Verify these type names match UMLS types and convert
			types = ["NCI:" + type_name for type_name in fields[7].split("|")]
			entity = entities.create(id, types, names, parents, {})
			entities_dict[id] = entity

if __name__ == '__main__':
    main()
