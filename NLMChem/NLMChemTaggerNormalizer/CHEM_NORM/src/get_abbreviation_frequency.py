import codecs
import datetime
import gzip
import json
import os

abbr_dirname = "/panfs/pan1.be-md.ncbi.nlm.nih.gov/bionlp/lulab/wei/Entire_Update_PMC/tmp/Ab3P/"
abbr_summary_filename = "data/abbr_frequency.txt.gz"

mappings = 0
abbr_dict = dict()

def main():
	
	filename_list = os.listdir(abbr_dirname)
	
	for filename in filename_list:
		if filename.endswith(".txt"):
			load_abbrfile(abbr_dirname + filename)

	print("Loaded " + str(len(abbr_dict)) + " short forms, with " + str(mappings) + " total mappings")
	write(abbr_summary_filename)

def load_abbrfile(filename):
	global mappings
	# Summarizes abbreviations file in TSV format
	print("Loading abbreviations from " + filename)
	with codecs.open(filename, 'r', encoding="utf8") as f:
		for line in f:
			# print(line)
			line = line.strip()
			fields = line.split("\t");
			if len(fields) == 3:
				short = fields[1]
				long = fields[2]
				if not short in abbr_dict:
					abbr_dict[short] = dict()
				if not long in abbr_dict[short]:
					abbr_dict[short][long] = 0
					mappings += 1
				abbr_dict[short][long] += 1
			else:
				print("WARN number of fields is not 3: \"" + line + "\"")

def write(filename):
	file = None
	if filename.endswith(".gz"):
		file = gzip.open(filename, 'wt', encoding="utf-8") 
	else:
		file = codecs.open(filename, 'w', encoding="utf-8") 
	# Write entities in JSON
	json.dump(abbr_dict, file, indent = 3)
	file.close()

if __name__ == '__main__':
    main()
