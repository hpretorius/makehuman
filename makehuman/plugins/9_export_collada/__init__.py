#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Thomas Larsson

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

from export import Exporter
from exportutils.config import Config


class DaeConfig(Config):
    def __init__(self):

        Config.__init__(self)

        self.useRelPaths = True
        self.useNormals = True

        self.useFaceRig =           True
        self.expressions = False
        self.useCustomTargets = False
        self.useTPose = False

        self.yUpFaceZ = True
        self.yUpFaceX = False
        self.zUpFaceNegY = False
        self.zUpFaceX = False

        self.localY = True
        self.localX = False
        self.localG = False

    # TODO preferably these are used (perhaps as enum) instead of the bools above
    # TODO move these to export Config super class
    @property
    def meshOrientation(self):
        if self.yUpFaceZ:
            return 'yUpFaceZ'
        if self.yUpFaceX:
            return 'yUpFaceX'
        if self.zUpFaceNegY:
            return 'zUpFaceNegY'
        if self.zUpFaceX:
            return 'zUpFaceX'
        return 'yUpFaceZ'

    @property
    def localBoneAxis(self):
        if self.localY:
            return 'y'
        if self.localX:
            return 'x'
        if self.localG:
            return 'g'
        return 'y'

    @property
    def upAxis(self):
        if self.meshOrientation.startswith('yUp'):
            return 1
        elif self.meshOrientation.startswith('zUp'):
            return 2

    '''
    @property
    def offsetVect(self):
        result = [0.0, 0.0, 0.0]
        result[self.upAxis] = self.offset
        return result
    '''

    def getRigOptions(self):
        rigOptions = super(DaeConfig, self).getRigOptions()
        if rigOptions is None:
            return None
        else:
            rigOptions.setExportOptions(
                useFaceRig = self.useFaceRig,
                useTPose = self.useTPose,
            )
        return rigOptions


class ExporterCollada(Exporter):
    def __init__(self):
        Exporter.__init__(self)
        self.name = "Collada (dae)"
        self.filter = "Collada (*.dae)"
        self.fileExtension = "dae"
        self.orderPriority = 95.0

    def build(self, options, taskview):
        import gui
        self.useFaceRig   = options.addWidget(gui.CheckBox("Face rig", True))
        Exporter.build(self, options, taskview)

        orients = []
        self.yUpFaceZ = options.addWidget(gui.RadioButton(orients, "Y up, face Z", True))
        self.yUpFaceX = options.addWidget(gui.RadioButton(orients, "Y up, face X", False))
        self.zUpFaceNegY = options.addWidget(gui.RadioButton(orients, "Z up, face -Y", False))
        self.zUpFaceX = options.addWidget(gui.RadioButton(orients, "Z up, face X", False))

        #csyses = []
        #self.localY = options.addWidget(gui.RadioButton(csyses, "Local Y along bone", True))
        #self.localX = options.addWidget(gui.RadioButton(csyses, "Local X along bone", False))
        #self.localG = options.addWidget(gui.RadioButton(csyses, "Local = Global", False))

    def export(self, human, filename):
        from .mh2collada import exportCollada
        #self.taskview.exitPoseMode()
        cfg = self.getConfig()
        cfg.setHuman(human)
        exportCollada(filename("dae"), cfg)
        #self.taskview.enterPoseMode()

    def getConfig(self):
        cfg = DaeConfig()
        cfg.useTPose           = False # self.useTPose.selected
        cfg.useFaceRig = self.useFaceRig.selected
        cfg.feetOnGround       = self.feetOnGround.selected
        cfg.scale,cfg.unit    = self.taskview.getScale()

        #cfg.expressions = self.expressions.selected
        #cfg.useCustomTargets = self.useCustomTargets.selected
        #cfg.useTPose = self.useTPose.selected

        cfg.yUpFaceZ = self.yUpFaceZ.selected
        cfg.yUpFaceX = self.yUpFaceX.selected
        cfg.zUpFaceNegY = self.zUpFaceNegY.selected
        cfg.zUpFaceX = self.zUpFaceX.selected

        #cfg.localY = self.localY.selected
        #cfg.localX = self.localX.selected
        #cfg.localG = self.localG.selected

        return cfg


def load(app):
    app.addExporter(ExporterCollada())

def unload(app):
    pass
