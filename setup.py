"""Cython build file"""
from __future__ import annotations

import os

from Cython.Build import cythonize
from distutils.core import setup
from distutils.extension import Extension

cythonExt = []
for root, dirs, files in os.walk(os.getcwd()):
    for file in files:
        if file.endswith(".pyx") and ".pyenv" not in root:  # im sorry
            filePath = os.path.relpath(os.path.join(root, file))
            cythonExt.append(Extension(filePath.replace("/", ".")[:-4], [filePath]))

setup(
    name="pep.pyx modules",
    ext_modules=cythonize(cythonExt, nthreads=4),
)
