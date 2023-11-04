#!/usr/bin/env python

import setuptools

with open('README.md') as f:
    long_description = f.read()


setuptools.setup(
    author='Lars Kellogg-Stedman',
    author_email='lars@oddbit.com',
    url='http://github.com/larsks/python-netns',
    description='Wrapper for the Linux setns() system call',
    long_description=long_description,
    name='netns',
    license='GPLv3',
    py_modules=['netns'],
    version='1.1',
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: Internet",
        "Topic :: System :: Networking",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)
