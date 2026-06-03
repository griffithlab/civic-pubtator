import codecs
import gzip
import json
import sys
import collections

filename = sys.argv[1]
print("Loading entities from " + filename)
entities_dict = dict()
if filename.endswith(".gz"):
	file = gzip.open(filename, 'rt', encoding="utf-8") 
else:
	file = codecs.open(filename, 'r', encoding="utf-8")
entities_dict = json.load(file)
file.close()

# First pass: get set of all primary IDs, the xref resources and the maximum number mapped of each
primary_ids = set()
resource2maxcount = dict()
for id, entity in entities_dict.items():
	primary_ids.add(id)
	if not "xrefs" in entity:
		continue
	resources = [xref.split(":")[0] for xref in entity["xrefs"]]
	resource_counts = collections.Counter(resources)
	for resource, count in resource_counts.items():
		if not resource in resource2maxcount:
			resource2maxcount[resource] = count
		elif resource2maxcount[resource] < count:
			resource2maxcount[resource] = count
print("Number of primary identifiers is {}".format(len(primary_ids)))
print("Number of xref resources is {}".format(len(resource2maxcount)))

resource2summary = {resource: [0] * (maxcount + 1) for resource, maxcount in resource2maxcount.items()}
for id, entity in entities_dict.items():
	if not "xrefs" in entity:
		continue
	resources = [xref.split(":")[0] for xref in entity["xrefs"]]
	resource_counts = collections.Counter(resources)
	for resource, count in resource_counts.items():
		resource2summary[resource][count] += 1

print("Xref Resource counts:")
for resource, summary in resource2summary.items():
	summary[0] = len(primary_ids) - sum(summary)
	print("{}\t{}".format(resource, "\t".join(map(str, summary))))
print("Done.")

