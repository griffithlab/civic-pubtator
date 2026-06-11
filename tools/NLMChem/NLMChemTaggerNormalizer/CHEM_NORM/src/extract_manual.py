import datetime

import entities

entites_filename="extracted/entities_manual.json.gz"
elements_filename="downloads/manual_elements.tsv"
manual_filename="downloads/manual_dict.tsv"

entities_dict = dict()

def main():
	load_manual(manual_filename)
	load_elements(elements_filename)

	print("Loaded " + str(len(entities_dict)) + " entities")
	print("Writing out dictionary, time = " + str(datetime.datetime.now()))
	entities.write(entities_dict, entites_filename)
	print("Done, time = " + str(datetime.datetime.now()))

def load_manual(filename):
	with open(filename) as f:
		for line in f:
			line = line.strip()
			# print(line)
			fields = line.split("\t")
			id = fields[0]
			names = fields[1].split("|")
			# Output record
			# print("ID = ", id)
			# print("names = ", names)
			entities_dict[id] = entities.create(id, set(), names, set(), set())

# TODO Update this so there is one column where isotopes are pipe-delimited, limit to common isotopes and add Technetium 99m
# Elements use a special format to handle all the isotopes
def load_elements(filename):
	with open(filename) as f:
		for line in f:
			line = line.strip()
			# print(line)
			fields = line.split("\t")
			id = fields[1]
			names = fields[2].split("|")
			symbol = fields[3]
			names2 = set()
			names2.add(symbol)
			for name in names:
				names2.add(name)
			# print("ID = ", id)
			# print("names = ", names2)
			entities_dict[id] = entities.create(id, set(), names2, set(), set())

if __name__ == '__main__':
    main()
