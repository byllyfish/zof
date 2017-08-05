"""A setuptools based setup module for zof.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import os
import re
from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))
README_PATH = os.path.join(HERE, 'README.rst')
VERSION_PATH = os.path.join(HERE, 'zof', '__init__.py')


def _get_description(path):
    with open(path, encoding='utf-8') as afile:
        return afile.read()


def _get_version(path):
    with open(path, encoding='utf-8') as afile:
        regex = re.compile(r"(?m)__version__\s*=\s*'(\d+\.\d+\.\d+)'")
        return regex.search(afile.read()).group(1)


setup(
    name='zof',
    packages=find_packages(exclude=['test']),
    version=_get_version(VERSION_PATH),
    license='MIT',

    description='OpenFlow App Framework',
    long_description=_get_description(README_PATH),
    keywords='openflow controller',

    # The project's main homepage and author.
    url='https://github.com/byllyfish/zof',
    author='William W. Fisher',
    author_email='william.w.fisher@gmail.com',

    # Dependencies
    install_requires=[
        # Imported by http submodule. Required for metrics demo.
        'aiohttp>=2.2.2',
        # Required for metrics demo.
        'prometheus_client',
        # Required for command_shell demo.
        'prompt_toolkit'
    ],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: System :: Networking'
    ],

    zip_safe=True,
    test_suite='test'
)
