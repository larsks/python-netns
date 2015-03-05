#!/usr/bin/env python

import setuptools

setuptools.setup(
    author       = 'Lars Kellogg-Stedman',
    author_email = 'lars@oddbit.com',
    url          = 'http://github.com/larsks/python-netns',
    description  = 'Wrapper for the Linux setns() system call',
    name         = 'netns',
    py_modules   = ['netns'],
    version      = 1,
)

