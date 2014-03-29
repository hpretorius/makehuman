#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

""" 
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Glynn Clements

**Copyright(c):**      MakeHuman Team 2001-2014

**Licensing:**         AGPL3 (http://www.makehuman.org/doc/node/the_makehuman_application.html)

    This file is part of MakeHuman (www.makehuman.org).

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

**Coding Standards:**  See http://www.makehuman.org/node/165

Abstract
--------

TODO
"""

import os
import numpy as np

from PyQt4 import QtCore, QtGui

def load(path):
    """
    Load an Image (data) from specified image file path.
    Or convert QImage to Image (data).
    """
    if isinstance(path, QtGui.QImage):
        im = path
    else:
        import getpath
        path = getpath.pathToUnicode(path)
        im = QtGui.QImage(path)
    if im.isNull():
        raise RuntimeError("unable to load image '%s'" % path)
    w, h = im.width(), im.height()
    alpha = im.hasAlphaChannel()
    im = im.convertToFormat(QtGui.QImage.Format_ARGB32)
    pixels = im.bits().asstring(h * w * 4)
    pixels = np.fromstring(pixels, dtype=np.uint32).reshape((h, w))
    del im

    a = (pixels >> 24).astype(np.uint8)
    r = (pixels >> 16).astype(np.uint8)
    g = (pixels >>  8).astype(np.uint8)
    b = (pixels >>  0).astype(np.uint8)
    del pixels

    if alpha:
        data = np.dstack((r,g,b,a))
    else:
        data = np.dstack((r,g,b))

    del a,r,g,b

    data = np.ascontiguousarray(data)

    return data

def toQImage(data):
    """
    Convert Image (data) to QImage.
    """
    h, w, d = data.shape

    data = data.astype(np.uint32)

    if d == 1:
        fmt = QtGui.QImage.Format_RGB32
        pixels = data[...,0] * 0x10101
    elif d == 2:
        fmt = QtGui.QImage.Format_ARGB32
        pixels = data[...,1] * 0x1000000 + data[...,0] * 0x10101
    elif d == 3:
        fmt = QtGui.QImage.Format_RGB32
        pixels = 0xFF000000 + data[...,0] * 0x10000 + data[...,1] * 0x100 + data[...,2]
    elif d == 4:
        fmt = QtGui.QImage.Format_ARGB32
        pixels = data[...,3] * 0x1000000 + data[...,0] * 0x10000 + data[...,1] * 0x100 + data[...,2]

    return QtGui.QImage(pixels.tostring(), w, h, w * 4, fmt)

def save(path, data):
    """
    Save Image (data) to file.
    """
    import getpath
    path = getpath.pathToUnicode(path)

    im = toQImage(data)
    format = "PNG" if path.lower().endswith('.thumb') else None
    if not im.save(path, format):
        raise RuntimeError('error saving image %s' % path)

