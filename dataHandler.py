# coding: utf8
import csv

def csv_handler(csvfile):
	with open(csvfile, 'r', newline='', encoding="utf-8") as csvfd:
		reader = csv.reader(csvfd)
		yield reader.__next__()	# extract the headers
		# we suppose the start 2 columns are primary.
		last_col1 = ''
		last_col2 = ''
		for row in reader:
			try:
				if not row[0]:
					row[0] = last_col1
				if not row[1]:
					row[1] = last_col2
				yield row
				last_col1 = row[0]
				last_col2 = row[1]
			except IndexError:
				pass
