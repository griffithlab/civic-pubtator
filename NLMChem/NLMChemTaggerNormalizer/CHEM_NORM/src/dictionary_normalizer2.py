import codecs
import datetime
import os
import re
import json
import gzip

import strings

class DictionaryNormalizer2:

	def __init__(self, config, target_filter):
		self.target_filter = target_filter
		self.unknown_id = config["unknown_id"]
		
		print("Loading allowed ID map")
		start = datetime.datetime.now()
		file = codecs.open(config["id2type_filename"], 'r', encoding="utf-8")
		self.allowed_ids = set()
		self.allowed_ids.add(self.unknown_id)
		for line in file:
			line = line.strip()
			if len(line) > 0:
				fields = line.split("\t")
				if fields[1].lower() == "true":
					self.allowed_ids.add(fields[0])
		file.close()
		print("Loaded " + str(len(self.allowed_ids)) + " allowed IDs")
		print("Elapsed = " + str(datetime.datetime.now() - start))
		
		print("Loading name to entity map")
		start = datetime.datetime.now()
		if config["name2ids_filename"].endswith(".gz"):
			with gzip.open(config["name2ids_filename"], "r") as name2ids_file:
				self.name2ids = {name: set(ids) for name, ids in json.load(name2ids_file).items()}
		else:
			with open(config["name2ids_filename"], "r") as name2ids_file:
				self.name2ids = {name: set(ids) for name, ids in json.load(name2ids_file).items()}
		print("Loaded " + str(len(self.name2ids)) + " names")
		print("Elapsed = " + str(datetime.datetime.now() - start))
		
		print("Creating entity to best name map")
		start = datetime.datetime.now()
		self.id2name = self.make_id2name()
		print("Created " + str(len(self.id2name)) + " ID to name mappings")
		print("Elapsed = " + str(datetime.datetime.now() - start))
		
		start = datetime.datetime.now()
		self.load_templates(config["c_template_cache_filename"], config["p_template_cache_filename"])
		print("Loaded " + str(len(self.c_template2names)) + " c_templates")
		print("Loaded " + str(len(self.p_template2names)) + " p_templates")
		print("Elapsed = " + str(datetime.datetime.now() - start))

		print("Loading entity to entity map")
		start = datetime.datetime.now()
		if config["id2ids_filename"].endswith(".gz"):
			with gzip.open(config["id2ids_filename"], "r") as id2ids_file:
				self.id2ids = json.load(id2ids_file)
		else:
			with open(config["id2ids_filename"], "r") as id2ids_file:
				self.id2ids = json.load(id2ids_file)
		print("Loaded " + str(len(self.id2ids)) + " ID to ID mappings")
		print("Elapsed = " + str(datetime.datetime.now() - start))

	# TODO PERFORMANCE Create non-logging version with shortcut logic
	def normalize_mention(self, mention_text):
		nlookup = self.name_lookup(mention_text)
		c_template, p_template = get_templates(mention_text)
		ctlookup = self.c_template_lookup(c_template)
		ptlookup = self.p_template_lookup(p_template)
		ectlookup = self.entities_lookup(ctlookup)
		pctlookup = self.entities_lookup(ptlookup)
		sieve = 0
		target_entities = self.filter_nontarget(nlookup)
		if len(target_entities) == 0:
			sieve = 1
			target_entities = self.filter_nontarget(ctlookup)
		if len(target_entities) == 0:
			sieve = 2
			target_entities = self.filter_nontarget(ptlookup)
		if len(target_entities) == 0:
			sieve = 3
			target_entities = self.filter_nontarget(ectlookup)
		if len(target_entities) == 0:
			sieve = 4
			target_entities = self.filter_nontarget(pctlookup)
		#print("LOOKUP\t" + mention_text + "\t" + c_template + "\t" + p_template + "\t" + str(nlookup) + "\t" + str(ctlookup) + "\t" + str(ptlookup) + "\t" + str(ectlookup) + "\t" + str(pctlookup) + "\t" + str(target_entities) + "\t" + str(sieve))
		return target_entities, sieve
		
	def load_templates(self, c_template_cache_filename, p_template_cache_filename):
		# Load from the cache if it exists
		if os.path.exists(c_template_cache_filename) and os.path.exists(p_template_cache_filename):
			print("Loading template to name maps from cache")
			if c_template_cache_filename.endswith(".gz"):
				with gzip.open(c_template_cache_filename, "r") as c_template_cache_file:
					self.c_template2names = {template: set(names) for template, names in json.load(c_template_cache_file).items()}
			else:
				with open(c_template_cache_filename, "r") as c_template_cache_file:
					self.c_template2names = {template: set(names) for template, names in json.load(c_template_cache_file).items()}
			if p_template_cache_filename.endswith(".gz"):
				with gzip.open(p_template_cache_filename, "r") as p_template_cache_file:
					self.p_template2names = {template: set(names) for template, names in json.load(p_template_cache_file).items()}
			else:
				with open(p_template_cache_filename, "r") as p_template_cache_file:
					self.p_template2names = {template: set(names) for template, names in json.load(p_template_cache_file).items()}
			return

		self.c_template2names = dict()
		self.p_template2names = dict()

		# Create templates
		print("Creating template to name map")
		for name in self.name2ids:
			c_template, p_template = get_templates(name)
			if not c_template in self.c_template2names:
				self.c_template2names[c_template] = set()
			self.c_template2names[c_template].add(name)
			if not p_template in self.p_template2names:
				self.p_template2names[p_template] = set()
			self.p_template2names[p_template].add(name)

		# Write cache to disk
		print("Writing template to name maps to cache")
		if c_template_cache_filename.endswith(".gz"):
			with gzip.open(c_template_cache_filename, "wt") as c_template_cache_file:
				json.dump({template: list(names) for template, names in self.c_template2names.items()}, c_template_cache_file, indent = 3)
		else:
			with open(c_template_cache_filename, "w") as c_template_cache_file:
				json.dump({template: list(names) for template, names in self.c_template2names.items()}, c_template_cache_file, indent = 3)
		if p_template_cache_filename.endswith(".gz"):
			with gzip.open(p_template_cache_filename, "wt") as p_template_cache_file:
				json.dump({template: list(names) for template, names in self.p_template2names.items()}, p_template_cache_file, indent = 3)
		else:
			with open(p_template_cache_filename, "w") as p_template_cache_file:
				json.dump({template: list(names) for template, names in self.p_template2names.items()}, p_template_cache_file, indent = 3)

	def make_id2name(self):
		# First pass
		name2ids2 = dict()
		for name, id_set in self.name2ids.items():
			name2 = name.lower()
			if name2 in name2ids2:
				name2ids2[name2].update(id_set)
			else:
				name2ids2[name2] = id_set.copy()
		# Second pass
		id2count = dict()
		id2name = dict()
		for name, id_set in self.name2ids.items():
			name2 = name.lower()
			count = len(name2ids2[name2])
			for id in id_set:
				if id in id2count:
					if count > id2count[id]:
						id2count[id] = count
						id2name[id] = name2
				else:
					id2count[id] = count
					id2name[id] = name2
		return id2name

	def filter_nontarget(self, entities):
		entities2 = set()
		for entity in entities:
			fields = entity.split(":")
			resource = fields[0]
			accession = fields[1]
			if self.target_filter(resource, accession):
				entities2.add(entity)
		return entities2

	def name_lookup(self, name):
		entities = set()
		if name in self.name2ids:
			lookup = self.name2ids[name]
			entities.update(lookup)
		return entities

	def c_template_lookup(self, template):
		entities = set()
		if template in self.c_template2names:
			for name in self.c_template2names[template]:
				if name in self.name2ids:
					entities.update(self.name2ids[name])
		return entities

	def p_template_lookup(self, template):
		entities = set()
		if template in self.p_template2names:
			for name in self.p_template2names[template]:
				if name in self.name2ids:
					entities.update(self.name2ids[name])
		return entities

	def entities_lookup(self, entities):
		entities2 = set()
		for entity in entities:
			if entity in self.id2ids:
				entities2.update(self.id2ids[entity])
		return entities2 - entities

def get_templates(name):
	# Map to ASCII, lower case
	c_template = strings.map_to_ASCII(name).lower()
	# Change non-alphanumeric characters to spaces
	c_template = re.sub("[^a-z0-9]", " ", c_template)
	# Change multiple spaces into a single space
	c_template = c_template.strip()
	c_template = re.sub("\\s+", " ", c_template)
	# Remove plurals
	p_template = stem_all(c_template)
	# Remove spaces between sequences besides digit digit
	same = p_template == c_template
	c_template = re.sub("([a-z]) ([a-z])", "\\1\\2", c_template)
	c_template = re.sub("([a-z]) ([0-9])", "\\1\\2", c_template)
	c_template = re.sub("([0-9]) ([a-z])", "\\1\\2", c_template)
	if same:
		p_template = c_template
	else:
		p_template = re.sub("([a-z]) ([a-z])", "\\1\\2", p_template)
		p_template = re.sub("([a-z]) ([0-9])", "\\1\\2", p_template)
		p_template = re.sub("([0-9]) ([a-z])", "\\1\\2", p_template)
	#print("Name \"" + name + "\" was processed to \"" + template + "\"")
	return c_template, p_template

def stem_all(name):
	# TODO Performance: should be faster to stem each, then use " ".join()
	# Note assumption that whitespace has been normalized
	fields = name.split(" ")
	name2 = ""
	for field in fields:
		name2 = name2 + " " + s_stem(field)
	return name2.strip()

def s_stem(str):
	# TODO compile these so it's faster
	# Note assumption str is already lowercase
	if not str.endswith("s"):
		return str
	# If word ends in "ies" but not "eies" or "aies" then "ies" --> "y"
	if (str.endswith("ies") and not str.endswith("eies") and not str.endswith("aies")):
		return re.sub("ies$", "y", str)
	# If a word ends in "es" but not "aes" "ees" or "oes" --> "es" --> "e"
	if (str.endswith("es") and not str.endswith("aes") and not str.endswith("ees") and not str.endswith("oes")):
		return re.sub("es$", "e", str)
	# If a word ends in "s" but not "us" or "ss" then "s" --> null
	if (not str.endswith("us") and not str.endswith("ss")):
		return re.sub("s$", "", str)
	# Return as-is
	return str

