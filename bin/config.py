# Use a JIT?
usePsyco = True

debugOnFailiure = False

# Create output directory relative to this config file.
import os.path
base, junk = os.path.split(__file__)
outputDirectory = os.path.normpath(os.path.join(base, '..', 'summaries'))

doDump = False
maskDumpErrors = False
doThreadCleanup = False

if True:
	testOnly = [
		('tests', 'test_full'),
		#('tests', 'test_canonical'),
		#('tests', 'test_graphalgorithims'),
		('tests', 'test_ipa'),
	]

testExclude = [
	# Known to be broken
	('tests', 'decompiler', 'test_exception'),
	]
