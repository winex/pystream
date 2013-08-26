# Copyright 2011 Nicholas Bray
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from distutils.core import setup, Extension

setup(name='_pystream',
	version='1.0',
	author='Nick Bray',
	ext_modules=[
		Extension(
			'_pystream', ['_pystream.cpp'],
			extra_compile_args = ['-fpermissive'],
			)
		]
	)

# TODO automatically copy into the library directory?
# NOTES
#python setup.py install --home=~ \
#                        --install-purelib=python/lib \
#                        --install-platlib=python/lib.$PLAT \
#                        --install-scripts=python/scripts
#                        --install-data=python/data
# This generates a .egg-info file?
