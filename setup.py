#! /usr/bin/env python
from setuptools import setup
import re
from os import path

with open('tweetfinder/__init__.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md')) as f:
    long_description = f.read()

setup(name='tweetfinder',
      version=version,
      description='Find tweets embedded and mentioned in news articles online.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Rahul Bhargava',
      author_email='r.bhargava@northeastern.edu',
      packages={'tweetfinder'},
      package_data={'': ['LICENSE']},
      include_package_data=True,
      install_requires=[
          "requests>=2.26.0",
          "readability-lxml>=0.8.1",
          "goose3>-3.1.9",
          "pycld2>=0.41",
          "beautifulsoup4>=4.9.3"
      ],
      license='Apache',
      zip_safe=False
)
