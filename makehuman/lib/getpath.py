#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Manuel Bastioni, Marc Flerackers, Glynn Clements

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

Utility module for finding the user home path.
"""

import sys
import os

__home_path = None

def pathToUnicode(path):
    """
    Unicode representation of the filename.
    String is decoded with the codeset used by the filesystem of the operating
    system.
    Unicode representations of paths are fit for use in GUI.
    If the path parameter is not a string, it will be returned unchanged.
    """
    if path is None:
        return path
    elif isinstance(path, unicode):
        return path
    elif isinstance(path, basestring):
        return path.decode(sys.getfilesystemencoding())
    else:
        return path

def formatPath(path):
    if path is None:
        return None
    return pathToUnicode( os.path.normpath(path).replace("\\", "/") )

def canonicalPath(path):
    """
    Return canonical name for location specified by path.
    Useful for comparing paths.
    """
    return formatPath(os.path.realpath(path))

def localPath(path):
    """
    Returns the path relative to the MH program directory,
    i.e. the inverse of canonicalPath. Needed to get
    human.targetsDetailStack keys from algos3d.targetBuffer keys.
    If all buffers use the same keys, this becomes obsolete.
    """
    path = os.path.realpath(path)
    root = os.path.realpath( getSysPath() )
    return formatPath(os.path.relpath(path, root))

def getHomePath():
    """
    Find the user home path.
    Note: If you are looking for MakeHuman data, you probably want getPath()!
    """
    # Cache the home path
    global __home_path
    if __home_path is not None:
        return __home_path

    # Windows
    if sys.platform == 'win32':
        import _winreg
        keyname = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        #name = 'Personal'
        k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, keyname)
        value, type_ = _winreg.QueryValueEx(k, 'Personal')
        if type_ == _winreg.REG_EXPAND_SZ:
            __home_path = formatPath(_winreg.ExpandEnvironmentStrings(value))
            return __home_path
        elif type_ == _winreg.REG_SZ:
            __home_path = formatPath(value)
            return __home_path
        else:
            raise RuntimeError("Couldn't determine user folder")

    # Unix-based
    else:
        __home_path = pathToUnicode( os.path.expanduser('~') )
        return __home_path

def getPath(subPath = ""):
    """
    Get MakeHuman folder that contains per-user files, located in the user home
    path.
    """
    path = getHomePath()

    # Windows
    if sys.platform == 'win32':
        path = os.path.join(path, "makehuman")

    # MAC OSX
    elif sys.platform.startswith("darwin"):
        path = os.path.join(path, "Documents")
        path = os.path.join(path, "MakeHuman")

    # Unix/Linux
    else:
        path = os.path.join(path, "makehuman")

    path = os.path.join(path, 'v1')

    if subPath:
        path = os.path.join(path, subPath)

    return formatPath(path)

def getDataPath(subPath = ""):
    """
    Path to per-user data folder, should always be the same as getPath('data').
    """
    if subPath:
        path = getPath( os.path.join("data", subPath) )
    else:
        path = getPath("data")
    return formatPath(path)

def getSysDataPath(subPath = ""):
    """
    Path to the data folder that is installed with MakeHuman system-wide.
    NOTE: do NOT assume that getSysPath("data") == getSysDataPath()!
    """
    if subPath:
        path = getSysPath( os.path.join("data", subPath) )
    else:
        path = getSysPath("data")
    return formatPath(path)

def getSysPath(subPath = ""):
    """
    Path to the system folder where MakeHuman is installed (it is possible that
    data is stored in another path).
    Writing to this folder or modifying this data usually requires admin rights,
    contains system-wide data (for all users).
    """
    if subPath:
        path = os.path.join('.', subPath)
    else:
        path = "."
    return formatPath(path)


def _allnamesequal(name):
    return all(n==name[0] for n in name[1:])

def commonprefix(paths, sep='/'):
    """
    Implementation of os.path.commonprefix that works as you would expect.

    Source: http://rosettacode.org/wiki/Find_Common_Directory_Path#Python
    """
    from itertools import takewhile

    bydirectorylevels = zip(*[p.split(sep) for p in paths])
    return sep.join(x[0] for x in takewhile(_allnamesequal, bydirectorylevels))

def isSubPath(subpath, path):
    """
    Verifies whether subpath is within path.
    """
    subpath = canonicalPath(subpath)
    path = canonicalPath(path)
    return commonprefix([subpath, path]) == path

def getRelativePath(path, relativeTo = [getDataPath(), getSysDataPath()]):
    """
    Return a relative file path, relative to one of the specified search paths.
    First valid path is returned, so order in which search paths are given matters.
    """
    if not isinstance(relativeTo, list):
        relativeTo = [relativeTo]

    relto = None
    for p in relativeTo:
        if isSubPath(path, p):
            relto = p
    if relto is None:
        return path

    return formatPath( os.path.relpath(path, relto) )

def findFile(relPath, searchPaths = [getDataPath(), getSysDataPath()]):
    """
    Inverse of getRelativePath: find an absolute path from specified relative
    path in one of the search paths.
    First occurence is returned, so order in which search paths are given matters.
    """
    if not isinstance(searchPaths, list):
        searchPaths = [searchPaths]

    for dataPath in searchPaths:
        path = os.path.join(dataPath, relPath)
        if os.path.isfile(path):
            return formatPath( path )

    return relPath

def search(paths, extensions, recursive=True, mutexExtensions=False):
    """
    Search for files with specified extensions in specified paths.
    If mutexExtensions is True, no duplicate files with only differing extension
    will be returned. Instead, only the file with highest extension precedence 
    (extensions occurs earlier in the extensions list) is kept.
    """
    if isinstance(paths, basestring):
        paths = [paths]
    if isinstance(extensions, basestring):
        extensions = [extensions]
    extensions = [e[1:].lower() if e.startswith('.') else e.lower() for e in extensions]

    if mutexExtensions:
        discovered = dict()
        def _aggregate_files_mutexExt(filepath):
            basep, ext = os.path.splitext(filepath)
            ext = ext[1:]
            if basep in discovered:
                if extensions.index(ext) < extensions.index(discovered[basep]):
                    discovered[basep] = ext
            else:
                discovered[basep] = ext

    if recursive:
        for path in paths:
            for root, dirs, files in os.walk(path):
                for f in files:
                    ext = os.path.splitext(f)[1][1:].lower()
                    if ext in extensions:
                        if mutexExtensions:
                            _aggregate_files_mutexExt(os.path.join(root, f))
                        else:
                            yield pathToUnicode( os.path.join(root, f) )
    else:
        for path in paths:
            if not os.path.isdir(path):
                continue
            for f in os.listdir(path):
                f = os.path.join(path, f)
                if os.path.isfile(f):
                    ext = os.path.splitext(f)[1][1:].lower()
                    if ext in extensions:
                        if mutexExtensions:
                            _aggregate_files_mutexExt(f)
                        else:
                            yield pathToUnicode( f )

    if mutexExtensions:
        for f in ["%s.%s" % (p,e) for p,e in discovered.items()]:
            yield pathToUnicode( f )

