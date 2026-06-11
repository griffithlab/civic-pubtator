import codecs
import collections
import datetime
import os
import sys

import bioc

def process_file(input_filename):
	abbreviations = set()
	reader = bioc.BioCXMLDocumentReader(input_filename)
	for document in reader:
		passage_abbrs = dict()
		for passage in document.passages:
			for annotation in passage.annotations:
				if annotation.infons.get("type") != "ABBR":
					continue
				passage_abbrs[(annotation.id, annotation.infons["ABBR"])] = annotation.text
			for relation in passage.relations:
				if relation.infons.get("type") != "ABBR":
					continue
				# format is document.id, short form, long form
				relation_abbr = dict()
				for node in relation.nodes:
					relation_abbr[node.role] = passage_abbrs[(node.refid, node.role)]
				abbreviations.add((document.id, relation_abbr["ShortForm"], relation_abbr["LongForm"]))
	print("Found " + str(len(abbreviations)))
	return abbreviations
		
if __name__ == "__main__":
	start = datetime.datetime.now()
	if len(sys.argv) != 3:
		print("Usage: <input> <output>")
		exit()
	input_path = sys.argv[1]
	output_path = sys.argv[2]
	
	abbreviations = set()
	start = datetime.datetime.now()
	if os.path.isdir(input_path):
		print("Processing directory " + input_path)
		# Process any xml files found
		dir = os.listdir(input_path)
		for item in dir:
			input_filename = input_path + "/" + item
			if os.path.isfile(input_filename) and input_filename.endswith(".xml"):
				print("Processing file " + input_filename)
				abbreviations.update(process_file(input_filename))
	elif os.path.isfile(input_path):
		print("Processing file " + input_path)
		# Process directly
		abbreviations.update(process_file(input_path))
	else:  
		raise RuntimeError("Path is not a directory or normal file: " + input_path)
	print("Total processing time = " + str(datetime.datetime.now() - start))

	# Open the file
	file = codecs.open(output_path, 'w', encoding="utf-8") 
	for document_ID, short, long in abbreviations:
		file.write("{}\t{}\t{}\n".format(document_ID, short, long))
	file.close()
