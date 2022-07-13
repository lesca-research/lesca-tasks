#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import os.path as op
from setuptools import setup, find_packages
import subprocess

version = {}
with open("lesca_tasks/version.py") as fp:
    exec(fp.read(), version)

here = op.abspath(op.dirname(__file__))

short_description = 'Lesca cognitive tasks'
long_description = short_description

setup(name='lesca_tasks', version=version['__version__'],
      description=short_description,
      long_description=long_description,
      author='Thomas Vincent', license='MIT',
      classifiers=['Development Status :: 3 - Alpha',
                   'Intended Audience :: Science/Research',
                   'License :: OSI Approved :: MIT License',
                   'Natural Language :: English',
                   'Natural Language :: French',
                   'Operating System :: POSIX :: Linux',
                   'Operating System :: MacOS',
                   'Operating System :: Microsoft :: Windows',
                   'Programming Language :: Python :: 3.8',],
      keywords='cognitive testing',
      packages=find_packages(exclude=['test']),
      python_requires='>=3',
      install_requires=['numpy', 'expyriment'],
      entry_points={
          'console_scripts': [
              'lesca_trigger_test = lesca_tasks.commands.trigger_test:main',
              'lesca_stroop_color = lesca_tasks.commands.stroop_color:main',
              'lesca_nback = lesca_tasks.commands.nback:main',
              'lesca_nback_walk = lesca_tasks.commands.nback_walk:main',
              'lesca_nmbam = lesca_tasks.commands.nmbam:main',
              'lesca_hbp = lesca_tasks.commands.hbp:main',
          ],
      })
