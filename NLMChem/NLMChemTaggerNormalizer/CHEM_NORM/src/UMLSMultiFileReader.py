import codecs
import gzip
import os

def open(folder, filename):
	obj = UMLSMultiFileReader(folder, filename)
	return iter(obj)

class UMLSMultiFileReader:
	
	def __init__(self, folder, filename):
		self.__filenames = list()
		self.__current_index = -1
		self.__current_file = None
		self.__current_line = None
		# Get list of matching names from folder
		for de in os.scandir(folder):
			if de.is_file() and de.name.startswith(filename):
				#print("Directory entry " + de.name + " starts with " + filename)
				self.__filenames.append(de.path)
		self.__filenames.sort()
		self.__increment_file()
	
	def __increment_file(self):
		if not self.__current_file is None:
			filename = self.__filenames[self.__current_index]
			print("Closing file " + filename)
			self.__current_file.close()
			self.__current_file = None
		self.__current_index += 1
		if self.__current_index < len(self.__filenames):
			filename = self.__filenames[self.__current_index]
			print("Reading from file " + filename)
			if filename.endswith(".gz"):
				self.__current_file = gzip.open(filename, 'rt', encoding="utf8") 
			else:
				self.__current_file = codecs.open(filename, 'r', encoding="utf8") 
			self.__current_line = next(self.__current_file)

	def __iter__(self):
		return self
		
	def __next__(self):
		# If no current file, done iterating
		if self.__current_file is None:
			raise StopIteration
		# Try to get next line
		try:
			next_line = next(self.__current_file)
		except StopIteration:
			next_line = None
		if next_line is None:
			# Handle the end of the file
			partial_line = self.__current_line
			self.__increment_file()
			if not self.__current_file is None:
				self.__current_line = partial_line + self.__current_line
				next_line = next(self.__current_file)
			# Otherwise __increment_file() didn't change __current_line, so return it
		return_line = self.__current_line
		self.__current_line = next_line
		return return_line
