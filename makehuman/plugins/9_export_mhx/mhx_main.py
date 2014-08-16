#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makeinfo.human.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Thomas Larsson

**Copyright(c):**      MakeHuman Team 2001-2014

**Licensing:**         AGPL3 (see also http://www.makeinfo.human.org/node/318)

**Coding Standards:**  See http://www.makeinfo.human.org/node/165

Abstract
--------

MakeHuman to MHX (MakeHuman eXchange format) exporter. MHX files can be loaded into Blender
"""

MAJOR_VERSION = 1
MINOR_VERSION = 18

import module3d
from core import G
import os
import time
import codecs
import numpy
import math
import log

#import cProfile

import proxy
import exportutils

from . import mhx_writer
from . import posebone
from . import mhx_materials
from . import mhx_mesh
from . import mhx_proxy
from . import mhx_armature
from . import mhx_pose


#-------------------------------------------------------------------------------
#   Export MHX file
#-------------------------------------------------------------------------------

def exportMhx(filepath, config):
    from .mhx_armature import setupArmature

    G.app.progress(0, text="Exporting MHX")
    log.message("Exporting %s" % filepath.encode('utf-8'))
    time1 = time.clock()
    human = config.human
    config.setupTexFolder(filepath)
    #config.setOffset(human)

    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    name = name.replace(" ","_").replace(":","_")
    #name = config.goodName(name)
    amt = setupArmature(name, human, config)
    fp = codecs.open(filepath, 'w', encoding='utf-8')
    fp.write(
        "# MakeHuman exported MHX\n" +
        "# www.makeinfo.human.org\n" +
        "MHX %d %d" % (MAJOR_VERSION, MINOR_VERSION))
    if amt:
        for key,value in amt.objectProps:
            fp.write(' %s:_%s' % (key.replace(" ","_"), value.replace('"','')))
    fp.write(
        " ;\n"  +
        "#if Blender24\n" +
        "  error 'This file can only be read with Blender 2.5' ;\n" +
        "#endif\n")

    if amt and config.scale != 1.0:
        amt.rescale(config.scale)
    proxies = config.getProxies()
    writer = Writer(name, human, amt, config, proxies)
    writer.writeFile(fp)
    fp.close()
    log.message("%s exported", filepath.encode('utf-8'))
    G.app.progress(1.0)


class Writer(mhx_writer.Writer):

    def __init__(self, name, human, amt, config, proxies):
        mhx_writer.Writer.__init__(self)

        self.name = name
        self.type = "mhx_main"
        self.human = human
        self.armature = amt
        self.config = config
        self.proxies = proxies
        self.customTargetFiles = exportutils.custom.listCustomFiles(config)

        self.matWriter = mhx_materials.Writer().fromOtherWriter(self)
        self.meshWriter = mhx_mesh.Writer().fromOtherWriter(self)
        self.proxyWriter = mhx_proxy.Writer(self.matWriter, self.meshWriter).fromOtherWriter(self)
        self.poseWriter = mhx_pose.Writer().fromOtherWriter(self)


    def writeFile(self, fp):
        amt = self.armature
        config = self.config

        fp.write("NoScale True ;\n")
        if amt:
            amt.writeGizmos(fp)
            G.app.progress(0.1, text="Exporting armature")
            amt.writeArmature(fp, MINOR_VERSION, self)
            amt.writeAction(fp)

        G.app.progress(0.15, text="Exporting materials")
        fp.write("\nNoScale False ;\n\n")
        self.matWriter.writeMaterials(fp)

        G.app.progress(0.25, text="Exporting main mesh")
        self.meshWriter.writeMesh(fp, self.human.getSeedMesh())

        self.proxyWriter.writeProxyType('Proxymeshes', 'T_Proxy', 3, fp, 0.35, 0.4)
        self.proxyWriter.writeProxyType('Clothes', 'T_Clothes', 2, fp, 0.4, 0.55)
        for ptype in proxy.SimpleProxyTypes:
            self.proxyWriter.writeProxyType(ptype, 'T_Clothes', 0, fp, 0.55, 0.6)

        self.poseWriter.writePose(fp)

        self.writeGroups(fp)
        if amt:
            amt.writeFinal(fp)


    def writeGroups(self, fp):
        amt = self.armature
        if amt:
            fp.write("PostProcess %s %s 0000003f 00080000 %s 0000c000 ;\n" % (self.meshName(), amt.name, amt.visibleLayers))
        else:
            fp.write("PostProcess %s %s 0000003f 00080000 00000000 0000c000 ;\n" % (self.meshName(), self.name))

        fp.write(
            "# ---------------- Groups -------------------------------- #\n\n" +
            "Group %s\n"  % self.name +
            "  Objects\n" +
            "    ob %s ;\n" % self.meshName())

        if amt:
            fp.write("    ob %s ;\n" % amt.name)

        self.groupProxy('Proxymeshes', 'T_Proxy', fp)
        self.groupProxy('Clothes', 'T_Clothes', fp)
        self.groupProxy('Hair', 'T_Clothes', fp)
        self.groupProxy('Eyes', 'T_Clothes', fp)
        self.groupProxy('Genitals', 'T_Clothes', fp)

        fp.write(
            "    ob CustomShapes ;\n" +
            "  end Objects\n" +
            "  layers Array 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1  ;\n" +
            "end Group\n")
        return


    def groupProxy(self, type, test, fp):
        for pxy in self.proxies.values():
            if pxy.type == type:
                fp.write("    ob %s ;\n" % self.meshName(pxy))

