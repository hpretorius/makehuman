#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Thomas Larsson, Jonas Hauquier

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

General skeleton, rig or armature class.
A skeleton is a hierarchic structure of bones, defined between a head and tail
joint position. Bones can be detached from each other (their head joint doesn't
necessarily need to be at the same position as the tail joint of their parent
bone).

A pose can be applied to the skeleton by setting a pose matrix for each of the
bones, allowing static posing or animation playback.
The skeleton supports skinning of a mesh using a list of vertex-to-bone
assignments.
"""

import math
from math import pi

import numpy as np
import numpy.linalg as la
import transformations as tm
import matrix

import log

D = pi/180


class Skeleton(object):

    def __init__(self, name="Skeleton"):
        self.name = name

        self.origin = np.zeros(3, dtype=np.float32)   # TODO actually use origin somewhere?

        self.bones = {}     # Bone lookup list by name
        self.boneslist = []  # Breadth-first ordered list of all bones
        self.roots = []     # Root bones of this skeleton, a skeleton can have multiple root bones.

    def __repr__(self):
        return ("  <Skeleton %s>" % self.name)

    def display(self):
        log.debug("<Skeleton %s", self.name)
        for bone in self.getBones():
            bone.display()
        log.debug(">")

    def canonalizeBoneNames(self):
        newBones = {}
        for bName, bone in self.bones.items():
            canonicalName = bName.lower().replace(' ','_').replace('-','_')
            bone.name = canonicalName
            newBones[bone.name] = bone
        self.bones = newBones

    def fromOptions(self, options, mesh):
        """
        Create armature from option set.
        Convert to skeleton.
        TODO: Merge Armature and Skeleton classes one day.
        """

        from armature.armature import setupArmature
        from core import G

        self._amt = amt = setupArmature("python", G.app.selectedHuman, options)
        for bone in amt.bones.values():
            self.addBone(bone.name, bone.parent, bone.head, bone.tail, bone.roll)

        self.build()

        # Normalize weights and put them in np format
        boneWeights = {}
        wtot = np.zeros(mesh.getVertexCount(), np.float32)
        for vgroup in amt.vertexWeights.values():
            for vn,w in vgroup:
                wtot[vn] += w

        for bname,vgroup in amt.vertexWeights.items():
            weights = np.zeros(len(vgroup), np.float32)
            verts = []
            n = 0
            for vn,w in vgroup:
                verts.append(vn)
                weights[n] = w/wtot[vn]
                n += 1
            boneWeights[bname] = (verts, weights)

        # Assign unweighted vertices to root bone with weight 1
        rootBone = self.roots[0].name
        informed = False
        if rootBone not in boneWeights.keys():
            boneWeights[rootBone] = ([], [])
        else:
            vs,ws = boneWeights[rootBone]
            boneWeights[rootBone] = (list(vs), list(ws))
        vs,ws = boneWeights[rootBone]
        for vIdx, wCount in enumerate(wtot):
            if wCount == 0:
                vs.append(vIdx)
                ws.append(1.0)
                if not informed:
                    log.debug("Adding trivial bone weights to bone %s for unweighted vertices.", rootBone)
                    informed = True
        boneWeights[rootBone] = (vs, np.asarray(ws, dtype=np.float32))

        return boneWeights

    def scaled(self, scale):
        """
        Create a scaled clone of this skeleton
        """
        result = type(self)(self.name)

        for bone in self.getBones():
            scaledHead = scale * bone.getRestHeadPos()
            scaledTail = scale * bone.getRestTailPos()
            parentName = bone.parent.name if bone.parent else None
            result.addBone(bone.name, parentName, scaledHead, scaledTail, bone.roll)

        result.build()

        return result

    def addBone(self, name, parentName, head, tail, roll=0):
        if name in self.bones.keys():
            raise RuntimeError("The skeleton %s already contains a bone named %s." % (self.__repr__(), name))
        bone = Bone(self, name, parentName, head, tail, roll)
        self.bones[name] = bone
        if not parentName:
            self.roots.append(bone)

    def build(self):
        self.__cacheGetBones()
        for bone in self.getBones():
            bone.build()

    def update(self):
        """
        Update skeleton pose matrices after setting a new pose.
        """
        for bone in self.getBones():
            bone.update()

    def updateJoints(self, humanMesh):
        """
        Update skeleton rest matrices to new joint positions after modifying
        human.
        """
        self._amt.updateJoints()
        for amtBone in self._amt.bones.values():
            bone = self.getBone(amtBone.name)
            bone.headPos[:] = amtBone.head
            bone.tailPos[:] = amtBone.tail
            bone.roll = amtBone.roll

        for bone in self.getBones():
            bone.build()

    def getBoneCount(self):
        return len(self.getBones())

    def getPose(self):
        """
        Retrieves the current pose of this skeleton as a list of pose matrices,
        one matrix per bone, bones in breadth-first order (same order as
        getBones()).

        returns     np.array((nBones, 4, 4), dtype=float32)
        """
        nBones = self.getBoneCount()
        poseMats = np.zeros((nBones,4,4),dtype=np.float32)

        for bIdx, bone in enumerate(self.getBones()):    # TODO eliminate loop?
            poseMats[bIdx] = bone.matPose

        return poseMats

    def setPose(self, poseMats):
        """
        Set pose of this skeleton as a list of pose matrices, one matrix per
        bone with bones in breadth-first order (same order as getBones()).

        poseMats    np.array((nBones, 4, 4), dtype=float32)
        """
        for bIdx, bone in enumerate(self.getBones()):
            bone.matPose = np.identity(4, dtype=np.float32)

            # Calculate rotations
            bone.matPose[:3,:3] = poseMats[bIdx,:3,:3]
            invRest = la.inv(bone.matRestGlobal)
            bone.matPose = np.dot(np.dot(invRest, bone.matPose), bone.matRestGlobal)

            # Add translations from original
            if poseMats.shape[2] == 4:
                bone.matPose[:3,3] = poseMats[bIdx,:3,3]
        # TODO avoid this loop, eg by storing a pre-allocated poseMats np array in skeleton and keeping a reference to a sub-array in each bone. It would allow batch processing of all pose matrices in one np call
        self.update()

    def isInRestPose(self):
        for bone in self.getBones():
            if not bone.isInRestPose():
                return False
        return True

    def setToRestPose(self):
        for bone in self.getBones():
            bone.setToRestPose()

    def skinMesh(self, meshCoords, vertBoneMapping):
        """
        Update (pose) assigned mesh using linear blend skinning.
        """
        # TODO try creating an array P(nBones,3,4) with pose matrices, and an array W(nCoord,nWeights(float)*2(int))
        # for 3 weights
        # cache meshCoords.transpose()  or .T (is this faster? difference?)
        #   http://jameshensman.wordpress.com/2010/06/14/multiple-matrix-multiplication-in-numpy/
        # use np.dot for matrix multiply or is using sum() and * faster?
        # coords = W[:,1] * P[W[:,0]] * meshCoords.transpose()[:] + W[:,3] * P[W[:,2]] * meshCoords.transpose()[:] + W[:,5] * P[W[:,4]] * meshCoords.transpose()[:]
        nVerts = len(meshCoords)
        coords = np.zeros((nVerts,3), float)
        if meshCoords.shape[1] != 4:
            meshCoords_ = np.ones((nVerts, 4), float)   # TODO also allow skinning vectors (normals)? -- in this case you need to renormalize normals, unless you only multiply each normal with the transformation with largest weight
            meshCoords_[:,:3] = meshCoords
            meshCoords = meshCoords_
            log.debug("Unoptimized data structure passed to skinMesh, this will incur performance penalty when used for animation.")
        for bname, mapping in vertBoneMapping.items():
            try:
                verts,weights = mapping
                bone = self.getBone(bname)
                vec = np.dot(bone.matPoseVerts, meshCoords[verts].transpose())
                vec *= weights
                coords[verts] += vec.transpose()[:,:3]
            except KeyError as e:
                log.warning("Could not skin bone %s: no such bone in skeleton (%s)" % (bname, e))

        return coords

    def getBones(self):
        """
        Returns linear list of all bones in breadth-first order.
        """
        return self.boneslist

    def __cacheGetBones(self):
        from Queue import deque

        result = []
        queue = deque(self.roots)
        while len(queue) > 0:
            bone = queue.popleft()
            bone.index = len(result)
            result.append(bone)
            queue.extend(bone.children)
        self.boneslist = result

    def getJointNames(self):
        """
        Returns a list of all joints defining the bone positions (minus end
        effectors for leaf bones). The names are the same as the corresponding
        bones in this skeleton.
        List is in depth-first order (usually the order of joints in a BVH file)
        """
        return self._retrieveJointNames(self.roots[0])

    def _retrieveJointNames(self, parentBone):
        result = [parentBone.name]
        for child in parentBone.children:
            result.extend(self._retrieveJointNames(child))
        return result

    def getBone(self, name):
        return self.bones[name]

    def containsBone(self, name):
        return name in self.bones.keys()

    def getBoneToIdxMapping(self):
        result = {}
        boneNames = [ bone.name for bone in self.getBones() ]
        for idx, name in enumerate(boneNames):
            result[name] = idx
        return result

    def compare(self, other):
        pass
        # TODO compare two skeletons (structure only)


class Bone(object):

    def __init__(self, skel, name, parentName, headPos, tailPos, roll=0):
        """
        Construct a new bone for specified skeleton.
        headPos and tailPos should be in world space coordinates (relative to root).
        parentName should be None for a root bone.
        """
        self.name = name
        self.skeleton = skel

        self.headPos = np.zeros(3,dtype=np.float32)
        self.headPos[:] = headPos[:3]
        self.tailPos = np.zeros(3,dtype=np.float32)
        self.tailPos[:] = tailPos[:3]

        self.roll = float(roll)
        self.length = 0
        self.yvector4 = None    # Direction vector of this bone

        self.children = []
        if parentName:
            self.parent = skel.getBone(parentName)
            self.parent.children.append(self)
        else:
            self.parent = None

        self.index = None   # The index of this bone in the breadth-first bone list

        # Matrices:
        # static
        #  matRestGlobal:     4x4 rest matrix, relative world
        #  matRestRelative:   4x4 rest matrix, relative parent
        # posed
        #  matPose:           4x4 pose matrix, relative parent and own rest pose
        #  matPoseGlobal:     4x4 matrix, relative world
        #  matPoseVerts:      4x4 matrix, relative world and own rest pose

        self.matRestGlobal = None
        self.matRestRelative = None
        self.matPose = None
        self.matPoseGlobal = None
        self.matPoseVerts = None

    def getRestMatrix(self, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
        """
        meshOrientation: What axis points up along the model, and which direction
                         the model is facing.
            allowed values: yUpFaceZ (0), yUpFaceX (1), zUpFaceNegY (2), zUpFaceX (3)

        localBoneAxis: How to orient the local axes around the bone, which axis
                       points along the length of the bone. Global (g )assumes the 
                       same axes as the global coordinate space used for the model.
            allowed values: y, x, g
        """
        #self.calcRestMatrix()  # TODO perhaps interesting method to replace the current
        return transformBoneMatrix(self.matRestGlobal, meshOrientation, localBoneAxis, offsetVect)

    def getRelativeMatrix(self, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
        restmat = self.getRestMatrix(meshOrientation, localBoneAxis, offsetVect)

        # TODO this matrix is possibly the same as self.matRestRelative, but with optional adapted axes
        if self.parent:
            parmat = self.parent.getRestMatrix(meshOrientation, localBoneAxis, offsetVect)
            return np.dot(la.inv(parmat), restmat)
        else:
            return restmat

    def getBindMatrix(self, offsetVect=[0,0,0]):
        #self.calcRestMatrix()
        self.matRestGlobal
        restmat = self.matRestGlobal.copy()
        restmat[:3,3] += offsetVect

        bindinv = np.transpose(restmat)
        bindmat = la.inv(bindinv)
        return bindmat,bindinv

    def __repr__(self):
        return ("  <Bone %s>" % self.name)

    def build(self):
        """
        Set matPoseVerts, matPoseGlobal and matRestRelative... TODO
        needs to happen after changing skeleton structure
        """
        # Set pose matrix to rest pose
        self.matPose = np.identity(4, np.float32)

        self.head3 = np.array(self.headPos[:3], dtype=np.float32)
        self.head4 = np.append(self.head3, 1.0)

        self.tail3 = np.array(self.tailPos[:3], dtype=np.float32)
        self.tail4 = np.append(self.head3, 1.0)

        # Update rest matrices
        self.length, self.matRestGlobal = getMatrix(self.head3, self.tail3, self.roll)
        if self.parent:
            self.matRestRelative = np.dot(la.inv(self.parent.matRestGlobal), self.matRestGlobal)
        else:
            self.matRestRelative = self.matRestGlobal

        self.vector4 = self.tail4 - self.head4
        self.yvector4 = np.array((0, self.length, 0, 1))

        # Update pose matrices
        self.update()

    def update(self):
        """
        Recalculate global pose matrix ... TODO
        Needs to happen after setting pose matrix
        Should be called after changing pose (matPose)
        """
        if self.parent:
            self.matPoseGlobal = np.dot(self.parent.matPoseGlobal, np.dot(self.matRestRelative, self.matPose))
        else:
            self.matPoseGlobal = np.dot(self.matRestRelative, self.matPose)

        try:
            self.matPoseVerts = np.dot(self.matPoseGlobal, la.inv(self.matRestGlobal))
        except:
            log.debug("Cannot calculate pose verts matrix for bone %s %s %s", self.name, self.getRestHeadPos(), self.getRestTailPos())
            log.debug("Non-singular rest matrix %s", self.matRestGlobal)

    def getHead(self):
        """
        The head position of this bone in world space.
        """
        return self.matPoseGlobal[:3,3].copy()

    def getTail(self):
        """
        The tail position of this bone in world space.
        """
        tail4 = np.dot(self.matPoseGlobal, self.yvector4)
        return tail4[:3].copy()

    def getLength(self):
        return self.yvector4[1]

    def getRestHeadPos(self):
        return self.headPos.copy()

    def getRestTailPos(self):
        return self.tailPos.copy()

    def getRestOffset(self):
        if self.parent:
            return self.getRestHeadPos() - self.parent.getRestHeadPos()
        else:
            return self.getRestHeadPos()

    def getRestDirection(self):
        return matrix.normalize(self.getRestOffset())

    def getRestOrientationQuat(self):
        return tm.quaternion_from_matrix(self.matRestGlobal)

    def getRoll(self):
        """
        The roll angle of this bone. (in rest)
        """
        R = self.matRestGlobal
        qy = R[0,2] - R[2,0];
        qw = R[0,0] + R[1,1] + R[2,2] + 1;

        if qw < 1e-4:
            roll = pi
        else:
            roll = 2*math.atan2(qy, qw);
        return roll

    def getName(self):
        return self.name

    def hasParent(self):
        return self.parent != None

    def isRoot(self):
        return not self.hasParent()

    def hasChildren(self):
        return len(self.children) > 0

    def setToRestPose(self):   # used to be zeroTransformation()
        """
        Reset bone pose matrix to default (identity).
        """
        self.matPose = np.identity(4, np.float32)
        self.update()

    def isInRestPose(self):
        return (self.matPose == np.identity(4, np.float32)).all()

    def setRotationIndex(self, index, angle, useQuat):
        """
        Set the rotation for one of the three rotation channels, either as
        quaternion or euler matrix. index should be 1,2 or 3 and represents
        x, y and z axis accordingly
        """
        if useQuat:
            quat = tm.quaternion_from_matrix(self.matPose)
            log.debug("%s", str(quat))
            quat[index] = angle/1000
            log.debug("%s", str(quat))
            _normalizeQuaternion(quat)
            log.debug("%s", str(quat))
            self.matPose = tm.quaternion_matrix(quat)
            return quat[0]*1000
        else:
            angle = angle*D
            ax,ay,az = tm.euler_from_matrix(self.matPose, axes='sxyz')
            if index == 1:
                ax = angle
            elif index == 2:
                ay = angle
            elif index == 3:
                az = angle
            mat = tm.euler_matrix(ax, ay, az, axes='sxyz')
            self.matPose[:3,:3] = mat[:3,:3]
            return 1000.0

    Axes = [
        np.array((1,0,0)),
        np.array((0,1,0)),
        np.array((0,0,1))
    ]

    def rotate(self, angle, axis, rotWorld):
        """
        Rotate bone with specified angle around given axis.
        Set rotWorld to true to rotate in world space, else rotation happens in
        local coordinates.
        Axis should be 0, 1 or 2 for rotation around x, y or z axis.
        """
        mat = tm.rotation_matrix(angle*D, Bone.Axes[axis])
        if rotWorld:
            mat = np.dot(mat, self.matPoseGlobal)
            self.matPoseGlobal[:3,:3] = mat[:3,:3]
            self.matPose = self.getPoseFromGlobal()
        else:
            mat = np.dot(mat, self.matPose)
            self.matPose[:3,:3] = mat[:3,:3]

    def setRotation(self, angles):
        """
        Sets rotation of this bone (in local space) as Euler rotation
        angles x,y and z.
        """
        ax,ay,az = angles
        mat = tm.euler_matrix(ax, ay, az, axes='szyx')
        self.matPose[:3,:3] = mat[:3,:3]

    def getRotation(self):
        """
        Get rotation matrix of rotation of this bone in local space.
        """
        qw,qx,qy,qz = tm.quaternion_from_matrix(self.matPose)
        ax,ay,az = tm.euler_from_matrix(self.matPose, axes='sxyz')
        return (1000*qw,1000*qx,1000*qy,1000*qz, ax/D,ay/D,az/D)

    def getPoseQuaternion(self):
        """
        Get quaternion of orientation of this bone in local space.
        """
        return tm.quaternion_from_matrix(self.matPose)

    def setPoseQuaternion(self, quat):
        """
        Set orientation of this bone in local space as quaternion.
        """
        self.matPose = tm.quaternion_matrix(quat)

    def stretchTo(self, goal, doStretch):
        """
        Orient bone to point to goal position. Set doStretch to true to
        position the tail joint at goal, false to maintain length of this bone.
        """
        length, self.matPoseGlobal = getMatrix(self.getHead(), goal, 0)
        if doStretch:
            factor = length/self.length
            self.matPoseGlobal[:3,1] *= factor
        pose = self.getPoseFromGlobal()

        az,ay,ax = tm.euler_from_matrix(pose, axes='szyx')
        rot = tm.rotation_matrix(-ay + self.roll, Bone.Axes[1])
        self.matPoseGlobal[:3,:3] = np.dot(self.matPoseGlobal[:3,:3], rot[:3,:3])
        #pose2 = self.getPoseFromGlobal()

    ## TODO decouple this specific method from general armature?
    ## It is used by constraints.py and is related to IK
    ## TODO maybe place in an extra IK armature class or a separate module?
    def poleTargetCorrect(self, head, goal, pole, angle):
        """
        Resolve a pole target type of IK constraint.
        http://www.blender.org/development/release-logs/blender-246/inverse-kinematics/
        """
        yvec = goal-head
        xvec = pole-head
        xy = np.dot(xvec, yvec)/np.dot(yvec,yvec)
        xvec = xvec - xy * yvec
        xlen = math.sqrt(np.dot(xvec,xvec))
        if xlen > 1e-6:
            xvec = xvec / xlen
            zvec = self.matPoseGlobal[:3,2]
            zlen = math.sqrt(np.dot(zvec,zvec))
            zvec = zvec / zlen
            angle0 = math.asin( np.dot(xvec,zvec) )
            rot = tm.rotation_matrix(angle - angle0, Bone.Axes[1])
            self.matPoseGlobal[:3,:3] = np.dot(self.matPoseGlobal[:3,:3], rot[:3,:3])

    def getPoseFromGlobal(self):
        """
        Returns the pose matrix for this bone (relative to parent and rest pose)
        calculated from its global pose matrix.
        """
        if self.parent:
            return np.dot(la.inv(self.matRestRelative), np.dot(la.inv(self.parent.matPoseGlobal), self.matPoseGlobal))
        else:
            return np.dot(la.inv(self.matRestRelative), self.matPoseGlobal)


YZRotation = np.array(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
ZYRotation = np.array(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))

def toZisUp3(vec):
    """
    Convert vector from MH coordinate system (y is up) to Blender coordinate
    system (z is up).
    """
    return np.dot(ZYRotation[:3,:3], vec)

def fromZisUp4(mat):
    """
    Convert matrix from Blender coordinate system (z is up) to MH coordinate
    system (y is up).
    """
    return np.dot(YZRotation, mat)

YUnit = np.array((0,1,0))

## TODO do y-z conversion inside this method or require caller to do it?
def getMatrix(head, tail, roll):
    """
    Calculate an orientation (rest) matrix for a bone between specified head
    and tail positions with given bone roll angle.
    Returns length of the bone and rest orientation matrix in global coordinates.
    """
    vector = toZisUp3(tail - head)
    length = math.sqrt(np.dot(vector, vector))
    if length == 0:
        vector = [0,0,1]
    else:
        vector = vector/length
    yproj = np.dot(vector, YUnit)

    if yproj > 1-1e-6:
        axis = YUnit
        angle = 0
    elif yproj < -1+1e-6:
        axis = YUnit
        angle = pi
    else:
        axis = np.cross(YUnit, vector)
        axis = axis / math.sqrt(np.dot(axis,axis))
        angle = math.acos(yproj)
    mat = tm.rotation_matrix(angle, axis)
    if roll:
        mat = np.dot(mat, tm.rotation_matrix(roll, YUnit))
    mat = fromZisUp4(mat)
    mat[:3,3] = head
    return length, mat

## TODO unused?  this is used by constraints.py, maybe should be moved there
def quatAngles(quat):
    """
    Convert a quaternion to euler angles.
    """
    qw = quat[0]
    if abs(qw) < 1e-4:
        return (0,0,0)
    else:
        return ( 2*math.atan(quat[1]/qw),
                 2*math.atan(quat[2]/qw),
                 2*math.atan(quat[3]/qw)
               )

def _normalizeQuaternion(quat):
    r2 = quat[1]*quat[1] + quat[2]*quat[2] + quat[3]*quat[3]
    if r2 > 1:
        r2 = 1
    if quat[0] >= 0:
        sign = 1
    else:
        sign = -1
    quat[0] = sign*math.sqrt(1-r2)

def getHumanJointPosition(human, jointName, rest_coord=True):
    """
    Get the position of a joint from the human mesh.
    This position is determined by the center of the joint helper with the
    specified name.
    """
    if not jointName.startswith("joint-"):
        jointName = "joint-" + jointName
    fg = human.meshData.getFaceGroup(jointName)
    v_idx = human.meshData.getVerticesForGroups([fg.name])
    if rest_coord:
        verts = human.getRestposeCoordinates()[v_idx]
    else:
        verts = human.meshData.getCoords(v_idx)
    return verts.mean(axis=0)

def loadRig(options, mesh):
    """
    Initializes a skeleton from an option set
    Returns the skeleton and vertex-to-bone weights.
    Weights are of format: {"boneName": [ (vertIdx, weight), ...], ...}
    """
    from armature.options import ArmatureOptions

    #rigName = os.path.splitext(os.path.basename(filename))[0]
    if not isinstance(options, ArmatureOptions):
        options = ArmatureOptions()
    skel = Skeleton("python")
    weights = skel.fromOptions(options, mesh)
    return skel, weights

def getProxyWeights(proxy, humanWeights):
    # TODO duplicate of proxy.getWeights()

    # Zip vertex indices and weights
    rawWeights = {}
    for (key, val) in humanWeights.items():
        indxs, weights = val
        rawWeights[key] = zip(indxs, weights)

    vertexWeights = proxy.getWeights(rawWeights)

    # TODO this normalization and unzipping is duplicated in module3d.getWeights()
    # Unzip and normalize weights (and put them in np format)
    boneWeights = {}
    wtot = np.zeros(proxy.object.getSeedMesh().getVertexCount(), np.float32)
    for vgroup in vertexWeights.values():
        for vn,w in vgroup:
            wtot[vn] += w

    for bname,vgroup in vertexWeights.items():
        weights = np.zeros(len(vgroup), np.float32)
        verts = []
        n = 0
        for vn,w in vgroup:
            verts.append(vn)
            weights[n] = w/wtot[vn]
            n += 1
        boneWeights[bname] = (verts, weights)

    return boneWeights


_Identity = np.identity(4, float)
_RotX = tm.rotation_matrix(math.pi/2, (1,0,0))
_RotY = tm.rotation_matrix(math.pi/2, (0,1,0))
_RotNegX = tm.rotation_matrix(-math.pi/2, (1,0,0))
_RotZ = tm.rotation_matrix(math.pi/2, (0,0,1))
_RotZUpFaceX = np.dot(_RotZ, _RotX)
_RotXY = np.dot(_RotNegX, _RotY)

def transformBoneMatrix(mat, meshOrientation='yUpFaceZ', localBoneAxis='y', offsetVect=[0,0,0]):
    """
    Transform orientation of bone matrix to fit the chosen coordinate system
    and mesh orientation.

    meshOrientation: What axis points up along the model, and which direction
                     the model is facing.
        allowed values: yUpFaceZ (0), yUpFaceX (1), zUpFaceNegY (2), zUpFaceX (3)

    localBoneAxis: How to orient the local axes around the bone, which axis
                   points along the length of the bone. Global (g )assumes the 
                   same axes as the global coordinate space used for the model.
        allowed values: y, x, g
    """

    # TODO this is not nice, but probably needs to be done before transforming the matrix
    # TODO perhaps add offset as argument
    mat = mat.copy()
    mat[:3,3] += offsetVect

    if meshOrientation == 0 or meshOrientation == 'yUpFaceZ':
        rot = _Identity
    elif meshOrientation == 1 or meshOrientation == 'yUpFaceX':
        rot = _RotY
    elif meshOrientation == 2 or meshOrientation == 'zUpFaceNegY':
        rot = _RotX
    elif meshOrientation == 3 or meshOrientation == 'zUpFaceX':
        rot = _RotZUpFaceX
    else:
        log.warning('invalid meshOrientation parameter %s', meshOrientation)
        return None

    if localBoneAxis.lower() == 'y':
        # Y along self, X bend
        return np.dot(rot, mat)

    elif localBoneAxis.lower() == 'x':
        # X along self, Y bend
        return np.dot(rot, np.dot(mat, _RotXY) )

    elif localBoneAxis.lower() == 'g':
        # Global coordinate system
        tmat = np.identity(4, float)
        tmat[:,3] = np.dot(rot, mat[:,3])
        return tmat

    log.warning('invalid localBoneAxis parameter %s', localBoneAxis)
    return None
