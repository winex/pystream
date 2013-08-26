from distutils.core import setup, Extension

setup(name='pybind',
	version='1.0',
	author='Nick Bray',
	ext_modules=[
		Extension(
			'pybind', ['pybind.cpp', 'vec3_wrap.cpp'],
			extra_compile_args = ['-fpermissive'],
			)
		]
	)
