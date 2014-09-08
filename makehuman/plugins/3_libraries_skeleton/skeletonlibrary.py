#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Jonas Hauquier

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

Main skeleton tab
"""

import mh
import gui
import gui3d
import log
from collections import OrderedDict
import filechooser as fc

import skeleton
import skeleton_drawing
import animation
import armature
from armature.options import ArmatureOptions
import getpath
import material

import numpy as np
import os

#------------------------------------------------------------------------------------------
#   class SkeletonAction
#------------------------------------------------------------------------------------------

class SkeletonAction(gui3d.Action):
    def __init__(self, name, library, before, after):
        super(SkeletonAction, self).__init__(name)
        self.library = library
        self.before = before
        self.after = after

    def do(self):
        self.library.chooseSkeleton(self.after)
        return True

    def undo(self):
        self.library.chooseSkeleton(self.before)
        return True


#------------------------------------------------------------------------------------------
#   class SkeletonLibrary
#------------------------------------------------------------------------------------------

class SkeletonLibrary(gui3d.TaskView):

    def __init__(self, category):
        gui3d.TaskView.__init__(self, category, 'Skeleton')
        self.debugLib = None
        self.amtOptions = ArmatureOptions()
        self.optionsSelector = None

        self.systemRigs = mh.getSysDataPath('rigs')
        self.userRigs = os.path.join(mh.getPath(''), 'data', 'rigs')
        self.rigPaths = [self.userRigs, self.systemRigs]
        if not os.path.exists(self.userRigs):
            os.makedirs(self.userRigs)
        self.extension = "rig"

        self.human = gui3d.app.selectedHuman

        self.selectedRig = None
        self.selectedBone = None

        self.oldSmoothValue = False

        self.humanChanged = False   # Used for determining when joints need to be redrawn

        self.skelMesh = None
        self.skelObj = None

        self.jointsMesh = None
        self.jointsObj = None

        self.selectedJoint = None

        self.oldHumanMat = self.human.material
        self.oldPxyMats = dict()

        #
        #   Display box
        #

        '''
        self.displayBox = self.addLeftWidget(gui.GroupBox('Display'))
        self.showHumanTggl = self.displayBox.addWidget(gui.CheckBox("Show human"))
        @self.showHumanTggl.mhEvent
        def onClicked(event):
            if self.showHumanTggl.selected:
                self.human.show()
            else:
                self.human.hide()
        self.showHumanTggl.setSelected(True)

        self.showJointsTggl = self.displayBox.addWidget(gui.CheckBox("Show joints"))
        @self.showJointsTggl.mhEvent
        def onClicked(event):
            if not self.jointsObj:
                return
            if self.showJointsTggl.selected:
                self.jointsObj.show()
            else:
                self.jointsObj.hide()
        self.showJointsTggl.setSelected(True)
        '''

        self.sysDataPath = mh.getSysDataPath('rigs')
        self.homeDataPath = mh.getPath('data/rigs')
        if not os.path.exists(self.homeDataPath):
            os.makedirs(self.homeDataPath)
        self.paths = [self.homeDataPath, self.sysDataPath]

        #
        #   Preset box
        #

        self.presetChooser = self.addRightWidget(fc.IconListFileChooser( \
                                                    self.paths,
                                                    'json',
                                                    'thumb',
                                                    name='Rig presets',
                                                    notFoundImage = mh.getSysDataPath('notfound.thumb'), 
                                                    noneItem = True, 
                                                    doNotRecurse = True))
        self.presetChooser.setIconSize(50,50)

        @self.presetChooser.mhEvent
        def onFileSelected(filename):
            self.rigPresetFileSelected(filename)

        self.infoBox = self.addLeftWidget(gui.GroupBox('Rig info'))
        self.boneCountLbl = self.infoBox.addWidget(gui.TextView('Bones: '))
        self.descrLbl = self.infoBox.addWidget(gui.TextView('Description: '))
        self.descrLbl.setSizePolicy(gui.QtGui.QSizePolicy.Ignored, gui.QtGui.QSizePolicy.Preferred)
        self.descrLbl.setWordWrap(True)

    def rigPresetFileSelected(self, filename, suppressAction = False):
        self.selectedRig = filename

        if not filename:
            self.amtOptions.reset(self.optionsSelector, useMuscles=False)
            self.descrLbl.setText("")
            self.updateSkeleton(useOptions=False)
            return

        descr = self.amtOptions.loadPreset(filename, self.optionsSelector)   # TODO clean up this design
        self.descrLbl.setTextFormat(["Description",": %s"], gui.getLanguageString(descr))
        self.updateSkeleton(suppressAction = suppressAction)

    def updateSkeleton(self, useOptions=True, suppressAction = False):
        if self.human.getSkeleton():
            oldSkelOptions = self.human.getSkeleton().options
        else:
            oldSkelOptions = None
        self.amtOptions.fromSelector(self.optionsSelector)
        if useOptions:
            string = "Change skeleton"
            options = self.amtOptions
        else:
            string = "Clear skeleton"
            options = None

        if suppressAction:
            self.chooseSkeleton(options)
        else:
            gui3d.app.do(SkeletonAction(string, self, oldSkelOptions, options))


    def onShow(self, event):
        gui3d.TaskView.onShow(self, event)
        if gui3d.app.settings.get('cameraAutoZoom', True):
            gui3d.app.setGlobalCamera()

        # Disable smoothing in skeleton library
        self.oldSmoothValue = self.human.isSubdivided()
        self.human.setSubdivided(False)

        self.oldHumanMat = self.human.material.clone()
        self.oldPxyMats = dict()
        xray_mat = material.fromFile(mh.getSysDataPath('materials/xray.mhmat'))
        self.human.material = xray_mat
        for pxy in self.human.getProxies(includeHumanProxy=False):
            obj = pxy.object
            self.oldPxyMats[pxy.uuid] = obj.material.clone()
            obj.material = xray_mat

        # Make sure skeleton is updated if human has changed
        if self.human.getSkeleton():
            self.drawSkeleton(self.human.getSkeleton())
            mh.redraw()


    def onHide(self, event):
        gui3d.TaskView.onHide(self, event)

        self.human.material = self.oldHumanMat
        for pxy in self.human.getProxies(includeHumanProxy=False):
            if pxy.uuid in self.oldPxyMats:
                pxy.object.material = self.oldPxyMats[pxy.uuid]

        # Reset smooth setting
        self.human.setSubdivided(self.oldSmoothValue)
        mh.redraw()


    def chooseSkeleton(self, options):
        """
        Load skeleton from an options set.
        """
        log.debug("Loading skeleton with options %s", options)

        if not options:
            # Unload current skeleton
            self.human.setSkeleton(None)
            if self.skelObj:
                # Remove old skeleton mesh
                self.removeObject(self.skelObj)
                self.human.removeBoundMesh(self.skelObj.name)
                self.skelObj = None
                self.skelMesh = None
            self.boneCountLbl.setTextFormat(["Bones",": %s"], "")
            #self.selectedBone = None

            if self.debugLib:
                self.debugLib.reloadBoneExplorer()
            return

        # Load skeleton definition from options
        skel, boneWeights = skeleton.loadRig(options, self.human.meshData)
        self.human.setSkeleton(skel, boneWeights)

        # Store a reference to the currently loaded rig
        self.human.getSkeleton().options = options

        #self.filechooser.selectItem(options)

        # (Re-)draw the skeleton
        skel = self.human.getSkeleton()
        self.drawSkeleton(skel)

        self.boneCountLbl.setTextFormat(["Bones",": %s"], self.human.getSkeleton().getBoneCount())

        if self.debugLib:
            self.debugLib.reloadBoneExplorer()


    def drawSkeleton(self, skel):
        if self.skelObj:
            # Remove old skeleton mesh
            self.removeObject(self.skelObj)
            self.human.removeBoundMesh(self.skelObj.name)
            self.skelObj = None
            self.skelMesh = None
            self.selectedBone = None

        # Create a mesh from the skeleton in rest pose
        skel.setToRestPose() # Make sure skeleton is in rest pose when constructing the skeleton mesh
        self.skelMesh = skeleton_drawing.meshFromSkeleton(skel, "Prism")
        self.skelMesh.priority = 100
        self.skelMesh.setPickable(False)
        self.skelObj = self.addObject(gui3d.Object(self.skelMesh, self.human.getPosition()) )
        self.skelObj.setShadeless(0)
        self.skelObj.setSolid(0)
        self.skelObj.setRotation(self.human.getRotation())

        # Add the skeleton mesh to the human AnimatedMesh so it animates together with the skeleton
        # The skeleton mesh is supposed to be constructed from the skeleton in rest and receives
        # rigid vertex-bone weights (for each vertex exactly one weight of 1 to one bone)
        mapping = skeleton_drawing.getVertBoneMapping(skel, self.skelMesh)
        self.human.addBoundMesh(self.skelMesh, mapping)

        # Store a reference to the skeleton mesh object for other plugins
        self.human.getSkeleton().object = self.skelObj
        mh.redraw()


    def drawJointHelpers(self):
        """
        Draw the joint helpers from the basemesh that define the default or
        reference rig.
        """
        if self.jointsObj:
            self.removeObject(self.jointsObj)
            self.jointsObj = None
            self.jointsMesh = None
            self.selectedJoint = None

        jointGroupNames = [group.name for group in self.human.meshData.faceGroups if group.name.startswith("joint-")]
        # TODO maybe define a getter for this list in the skeleton module
        jointPositions = []
        for groupName in jointGroupNames:
            jointPositions.append(skeleton.getHumanJointPosition(self.human, groupName))

        self.jointsMesh = skeleton_drawing.meshFromJoints(jointPositions, jointGroupNames)
        self.jointsMesh.priority = 100
        self.jointsMesh.setPickable(False)
        self.jointsObj = self.addObject( gui3d.Object(self.jointsMesh, self.human.getPosition()) )
        self.jointsObj.setRotation(self.human.getRotation())

        color = np.asarray([255, 255, 0, 255], dtype=np.uint8)
        self.jointsMesh.color[:] = color[None,:]
        self.jointsMesh.markCoords(colr=True)
        self.jointsMesh.sync_color()

        mh.redraw()


    def showBoneWeights(self, boneName, boneWeights):
        mesh = self.human.meshData
        try:
            weights = np.asarray(boneWeights[boneName][1], dtype=np.float32)
            verts = boneWeights[boneName][0]
        except:
            return
        red = np.maximum(weights, 0)
        green = 1.0 - red
        blue = np.zeros_like(red)
        alpha = np.ones_like(red)
        color = np.array([red,green,blue,alpha]).T
        color = (color * 255.99).astype(np.uint8)
        mesh.color[verts,:] = color
        mesh.markCoords(verts, colr = True)
        mesh.sync_all()


    def highlightBone(self, name):
        if self.debugLib is None:
            return

        # Highlight bones
        self.selectedBone = name
        setColorForFaceGroup(self.skelMesh, self.selectedBone, [216, 110, 39, 255])
        gui3d.app.statusPersist(name)

        # Draw bone weights
        boneWeights = self.human.getVertexWeights()
        self.showBoneWeights(name, boneWeights)

        gui3d.app.redraw()


    def removeBoneHighlights(self):
        if self.debugLib is None:
            return

        # Disable highlight on bone
        if self.selectedBone:
            setColorForFaceGroup(self.skelMesh, self.selectedBone, [255,255,255,255])
            gui3d.app.statusPersist('')

            self.clearBoneWeights()
            self.selectedBone = None

            gui3d.app.redraw()


    def clearBoneWeights(self):
        mesh = self.human.meshData
        mesh.color[...] = (255,255,255,255)
        mesh.markCoords(colr = True)
        mesh.sync_all()

    def onHumanChanged(self, event):
        human = event.human
        if event.change == 'reset':
            if self.isShown():
                # Refresh onShow status
                self.onShow(event)

    def onHumanChanging(self, event):
        if event.change == 'reset':
            self.chooseSkeleton(None)
            self.presetChooser.selectItem(None)


    def onHumanRotated(self, event):
        if self.skelObj:
            self.skelObj.setRotation(gui3d.app.selectedHuman.getRotation())
        if self.jointsObj:
            self.jointsObj.setRotation(gui3d.app.selectedHuman.getRotation())


    def onHumanTranslated(self, event):
        if self.skelObj:
            self.skelObj.setPosition(gui3d.app.selectedHuman.getPosition())
        if self.jointsObj:
            self.jointsObj.setPosition(gui3d.app.selectedHuman.getPosition())

    def loadHandler(self, human, values):
        if values[0] == "skeleton":
            skelFile = values[1]

            skelFile = getpath.findFile(skelFile, self.paths)
            if not os.path.isfile(skelFile):
                log.warning("Could not load rig %s, file does not exist." % skelFile)
            else:
                self.rigPresetFileSelected(skelFile, True)
            return

    def saveHandler(self, human, file):
        if human.getSkeleton():
            rigFile = getpath.getRelativePath(self.selectedRig, self.paths)
            file.write('skeleton %s\n' % rigFile)



def setColorForFaceGroup(mesh, fgName, color):
    if mesh is None:
        return
    color = np.asarray(color, dtype=np.uint8)
    try:
        groupVerts = mesh.getVerticesForGroups([fgName])
        mesh.color[groupVerts] = color[None,:]
    except KeyError:
        return
    mesh.markCoords(colr=True)
    mesh.sync_color()
