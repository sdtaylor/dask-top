#!/usr/bin/python

# Copyright (C) 2020 Shawn Taylor
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# This implementation was modified from version 0.1 of s-tui
# See https://github.com/amanusk/s-tui

from __future__ import absolute_import

from setuptools import setup

setup(
    name="dask-top",
    packages=['dask_top', 'dask_top.ext', 'dask_top.menus'],
    version=0.1,
    author="Shawn Taylor",
    author_email="",
    description="CLI Status viewer for dask distributed schedulers",
    #long_description=open('README.md', 'r').read(),
    #long_description_content_type='text/markdown',
    license="GPLv2",
    url="https://github.com/sdtaylor/dask-top",
    keywords=['dask', 'top', 'distributed'],

    entry_points={
        'console_scripts': ['dask-top=dask_top.dask_top:main']
    },
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Monitoring',
    ],
    install_requires=[
        'urwid>=2.0.0',
    ],
)
