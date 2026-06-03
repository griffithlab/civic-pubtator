import unittest

import strings

class TestStrings(unittest.TestCase):

	def test_map_to_ASCII(self):
		# Test empty
		self.assertEqual("", strings.map_to_ASCII(""))

		# Check letters in ASCII range
		self.assertEqual("The quick brown fox jumped over the lazy dog.", strings.map_to_ASCII("The quick brown fox jumped over the lazy dog."))
		self.assertEqual(strings.map_to_ASCII(u"sodium bicarbonate"), "sodium bicarbonate")
	
		# Test Greek
		self.assertEqual(strings.map_to_ASCII(u"1,25\u03B1-dihydroxyvitamin D3"), "1,25alpha-dihydroxyvitamin D3")
		self.assertEqual(strings.map_to_ASCII(u"1\u03B1,25-(OH)2-vitamin D3"), "1alpha,25-(OH)2-vitamin D3")
		self.assertEqual(strings.map_to_ASCII(u"24-methylenecycloartan-3-\u03B2-ol"), "24-methylenecycloartan-3-beta-ol")
		self.assertEqual(strings.map_to_ASCII("3\u03B1,7\u03B1-dihydroxy-5\u03B2-cholan-24-oic acid"), "3alpha,7alpha-dihydroxy-5beta-cholan-24-oic acid")
		self.assertEqual(strings.map_to_ASCII(u"C\u03B2"), "C beta")
		self.assertEqual(strings.map_to_ASCII("Neu5Ac\u03B1"), "Neu5Ac alpha")
		self.assertEqual(strings.map_to_ASCII("\u03B2ME"), "beta ME")
		self.assertEqual(strings.map_to_ASCII("17\u03B2-estradiol"), "17beta-estradiol")
		self.assertEqual(strings.map_to_ASCII(u"NF-\u03BAB signaling pathways"), "NF-kappa B signaling pathways")
		self.assertEqual(strings.map_to_ASCII(u"\u03C0"), "pi")

		# Test Cyrillic look-alikes
		self.assertEqual(strings.map_to_ASCII(u"N\u04302CO3"), "Na2CO3")
		self.assertEqual(strings.map_to_ASCII("\u0412\u041D\u0421\u0425"), "BHPX")
		self.assertEqual(strings.map_to_ASCII("\u0432\u043D\u0441\u0445"), "bhpx")
		self.assertEqual("ABEMHOPX", strings.map_to_ASCII("\u0410\u0412\u0415\u041C\u041D\u041E\u0421\u0425"))
		self.assertEqual("abemhopx", strings.map_to_ASCII("\u0430\u0432\u0435\u043C\u043D\u043E\u0441\u0445"))

		# Test accents / diacritics
		self.assertEqual(strings.map_to_ASCII("Gö6976"), "Go6976")
		self.assertEqual(strings.map_to_ASCII(u"\xe0\xe7\xeb\xed\xf1\xf6\xfd\u0142\u015B"), "aceinoyls")

		# Test suppressed
		self.assertEqual(strings.map_to_ASCII(u"Lipofectamine\u2122 2000"), "Lipofectamine 2000")
		self.assertEqual(strings.map_to_ASCII(u"Lipofectamine\u21222000 Reagent"), "Lipofectamine 2000 Reagent")

		# Test spacing
		self.assertEqual(strings.map_to_ASCII(u"dioxane\u2009+\u2009water"), "dioxane + water")
		self.assertEqual("a b c d e f g h i j k l m", strings.map_to_ASCII("a b\u2000c\u2001d\u2002e\u2003f\u2004g\u2005h\u2006i\u2007j\u2008k\u2009l\u200Am"))
		self.assertEqual("a b", strings.map_to_ASCII("a\u00A0b"))

		# Test hyphens
		self.assertEqual("a-b-c-d-e-f--g--h-ij-k--l", strings.map_to_ASCII(u"a-b\u2010c\u2011d\u2012e\u2013f\u2014g\u2015h\u2212i\xADj\u002Dk\u2043l"))
		self.assertEqual(strings.map_to_ASCII(u"\u03B2\u2010cycloitral"), "beta-cycloitral")

		# Check apostrophes and quotes
		self.assertEqual("a'b'c'd'e`f", strings.map_to_ASCII("a'b\u2018c\u2019d\u2032e\u2035f"))
		self.assertEqual("a\"b\"c\"d''e``f", strings.map_to_ASCII("a\"b\u201Cc\u201Dd\u2033e\u2036f"))
		# Check Others
		self.assertEqual("a b*c+-d(c)e(r)f g-h", strings.map_to_ASCII("a b\xB7c\xB1d\xA9e\xAEf\u2122g\u2192h"))
		
if __name__ == '__main__':
	unittest.main()
