import gzip
import codecs
import json
import re

# Needs requests and beautifulsoup4
import requests
from bs4 import BeautifulSoup

import entities

entities_filename = "extracted/entities_MF.json"
website_url = requests.get("https://en.wikipedia.org/wiki/Glossary_of_chemical_formulae").text
soup = BeautifulSoup(website_url, "lxml")

entities_dict = dict()
tables = soup.find_all("table",{"class":"wikitable sortable"})
for table in tables:
	rows = table.find_all("tr")
	for row in rows:
		cells = row.find_all("td")
		cells.reverse()
		if len(cells) == 2 or len(cells) == 3:
			entity = dict()
			if len(cells) == 3:
				formula = cells.pop().text.strip()
			# Otherwise we re-use the previous formula
			print("formula = {}".format(formula))
			names = cells.pop().text.strip().split("  ")
			print("names = {}".format(names))
			identifier_CAS = cells.pop().text.strip()
			if len(identifier_CAS) == 0:
				continue
			if re.match("^[0-9][0-9]*-[0-9][0-9]-[0-9]$", identifier_CAS) is None:
				print("WARN CAS identfier does not match pattern: {}".format(identifier_CAS))
				continue
			id = "CAS:" + identifier_CAS
			entity["id"] = id
			names.append(formula)
			entity["names"] = names
			entities_dict[id] = entity
		else:
			print("WARN: Ignoring row \"{}\"".format(row.text.strip()))

entities.write(entities_dict, entities_filename)
print("Done.")