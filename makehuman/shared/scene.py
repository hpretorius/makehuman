#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    http://code.google.com/p/makehuman/

**Authors:**           Thanasis Papoutsidakis

**Copyright(c):**      MakeHuman Team 2001-2014

**Licensing:**         AGPL3 (see also http://www.makehuman.org/node/318)

**Coding Standards:**  See http://www.makehuman.org/node/165

Abstract
--------

Definitions of scene objects and the scene class.
.mhscene file structure.
"""

import pickle

import log
import events3d
from material import Color

mhscene_version = 5
mhscene_minversion = 5


class FileVersionException(Exception):
    def __init__(self, reason=None):
        Exception.__init__(self)
        self.reason = reason

    def __str__(self):
        if self.reason is None:
            erstr = "Incompatible file version"
        elif self.reason == "#too old":
            erstr =\
"The version of this file is no more supported by this version of MakeHuman."
        elif self.reason == "#too new":
            erstr =\
"The version of MakeHuman you are using is too old to open this file."
        else:
            erstr = repr(self.reason)
        return erstr


def checkVersions(versions, version_exception_class=None):
    if versions[0] is not None and versions[1] < versions[0]:
        if version_exception_class is not None:
            raise version_exception_class("#too old")
        return False
    elif versions[2] is not None and versions[1] > versions[2]:
        if version_exception_class is not None:
            raise version_exception_class("#too new")
        return False
    else:
        return True


class SceneObject(object):
    def __init__(self, scene=None, attributes={}):
        object.__init__(self)
        self._attributes = sorted(attributes.keys())
        self._attrver = {}

        for (attrname, attr) in attributes.items():

            # Version control system for backwards compatibility
            # with older mhscene files.
            # Usage: 'attribute': [attribute, minversion]
            # Or: 'attribute': [attribute, (minversion, maxversion)]
            # Or: 'attribute':
            #     [attribute, [(minver1, maxver1), (minver2, maxver2), ...]]
            attribute = None
            if isinstance(attr, list):
                attribute = attr[0]
                if isinstance(attr[1], list):
                    self._attrver[attrname] = attr[1]
                elif isinstance(attr[1], tuple):
                    self._attrver[attrname] = [attr[1]]
                else:
                    self._attrver[attrname] = [(attr[1], None)]
            else:
                attribute = attr
                self._attrver[attrname] = [(None, None)]

            object.__setattr__(self, "_" + attrname, attribute)

        self._scene = scene

    def __getattr__(self, attr):
        if attr in object.__getattribute__(self, "_attributes"):
            return object.__getattribute__(self, "_" + attr)
        elif hasattr(self, attr):
            return object.__getattribute__(self, attr)
        else:
            raise AttributeError(
                '"%s" type scene objects do not have any "%s" attribute.'
                % (type(self), attr))

    def __setattr__(self, attr, value):
        if hasattr(self, "_attributes") and attr in self._attributes:
            attrValue = getattr(self, "_" + attr)
            if isinstance(attrValue, Color):
                # Ensure Color attributes are of type Color
                value = Color(value)
            if (attrValue != value):
                object.__setattr__(self, "_" + attr, value)
                self.changed()
        else:
            object.__setattr__(self, attr, value)

    def changed(self):
        if (self._scene is not None):
            self._scene.changed()

    def getAttributes(self):
        return self._attributes

    def save(self, hfile):
        for attr in self._attributes:
            pickle.dump(getattr(self, "_" + attr), hfile)

    def load(self, hfile):
        for attr in self._attributes:

            # Check if attribute exists in the file by checking
            # the compatibility of their versions
            filever = self._scene.filever
            supported = False
            for verlim in self._attrver[attr]:
                if checkVersions((verlim[0], filever, verlim[1])):
                    supported = True
                    break

            if supported:
                attrV = pickle.load(hfile)
                if isinstance(getattr(self, "_" + attr), Color):
                    setattr(self, "_" + attr, Color(attrV))
                else:
                    setattr(self, "_" + attr, attrV)


class Light(SceneObject):
    def __init__(self, scene=None):
        SceneObject.__init__(
            self, scene,
            attributes=
            {'position': (-10.99, 20.0, 20.0),
             'focus': (0.0, 0.0, 0.0),
             'color': Color(1.0, 1.0, 1.0),
             'specular': [Color(1.0, 1.0, 1.0), 5],
             'fov': 180.0,
             'attenuation': 0.0,
             'areaLights': 1,
             'areaLightSize': 4.0})


class Environment(SceneObject):
    def __init__(self, scene=None):
        SceneObject.__init__(
            self, scene,
            attributes=
            {'ambience': Color(0.3, 0.3, 0.3),
             'skybox': None})


class Scene(events3d.EventHandler):
    def __init__(self, path=None):
        if path is None:
            self.lights = [Light(self)]
            self.environment = Environment(self)

            self.unsaved = False
            self.path = None
        else:
            self.load(path)

    def changed(self):
        self.unsaved = True
        self.callEvent('onChanged', self)

    # Load scene from a .mhscene file.
    def load(self, path):
        log.debug('Loading scene file: %s', path)

        try:
            hfile = open(path, 'rb')
        except IOError as e:
            log.warning('Could not load %s: %s', path, e[1])
            return False
        else:
            try:
                # Ensure the file version is supported
                filever = pickle.load(hfile)
                checkVersions((mhscene_minversion, filever, mhscene_version),
                    FileVersionException)
                self.filever = filever

                self.environment.load(hfile)
                nlig = pickle.load(hfile)
                self.lights = []
                for i in xrange(nlig):
                    light = Light(self)
                    light.load(hfile)
                    self.lights.append(light)
            except FileVersionException as e:
                log.error('%s: %s', path, e)
                hfile.close()
                return False
            except:
                hfile.close()
                raise
            hfile.close()

        self.path = path
        self.unsaved = False
        self.callEvent('onChanged', self)
        return True

    # Reloads the loaded scene.
    # Useful when the scene file is changed from another Scene object.
    def reload(self):
        return self.load(self.path)

    # Save scene to a .mhscene file.
    def save(self, path=None):
        if path is None:
            path = self.path
        log.debug('Saving scene file: %s', path)

        try:
            hfile = open(path, 'wb')
        except IOError as e:
            log.warning('Could not save %s: %s', path, e[1])
            return False
        else:
            try:
                pickle.dump(mhscene_version, hfile)
                self.environment.save(hfile)
                pickle.dump(len(self.lights), hfile)
                for light in self.lights:
                    light.save(hfile)
            except:
                hfile.close()
                raise
            hfile.close()

        self.path = path
        self.unsaved = False
        return True

    def close(self):
        self.__init__()

    def addLight(self):
        self.changed()
        newlight = Light(self)
        self.lights.append(newlight)

    def removeLight(self, light):
        self.changed()
        self.lights.remove(light)
