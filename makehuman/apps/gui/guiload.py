#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Marc Flerackers

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

This module implements the 'Files > Load' tab 
"""

import os

import mh
import gui3d
import filechooser as fc
import qtgui as gui

class HumanFileSort(fc.FileSort):
    
    def __init__(self):
        
        super(HumanFileSort, self).__init__()
        self.meta = {}
    
    def fields(self):
        return list(super(HumanFileSort, self).fields())
        # TODO
        #return list(super(HumanFileSort, self).fields()) + ["gender", "age", "muscle", "weight"]

    def sortGender(self, filenames):

        self.updateMeta(filenames)
        decorated = self._getDecorated(lambda filename: self.meta[filename]['gender'], filenames)
        return self._decoratedSort(decorated)
        
    def sortAge(self, filenames):

        self.updateMeta(filenames)
        decorated = self._getDecorated(lambda filename: self.meta[filename]['age'], filenames)
        return self._decoratedSort(decorated)

    def sortMuscle(self, filenames):

        self.updateMeta(filenames)
        decorated = self._getDecorated(lambda filename: self.meta[filename]['muscle'], filenames)
        return self._decoratedSort(decorated)
       
    def sortWeight(self, filenames):

        self.updateMeta(filenames)
        decorated = self._getDecorated(lambda filename: self.meta[filename]['weight'], filenames)
        return self._decoratedSort(decorated)

    def updateMeta(self, filenames):
        
        for filename in filenames:
            if filename in self.meta:
                if self.meta[filename]['modified'] < os.path.getmtime(filename):
                    self.meta[filename] = self.getMeta(filename)
            else:
                self.meta[filename] = self.getMeta(filename)
                
    def getMeta(self, filename):
        
        meta = {}
                
        meta['modified'] = os.path.getmtime(filename)
        from codecs import open
        f = open(filename, 'rU', encoding="utf-8")
        for line in f:
            lineData = line.split()
            field = lineData[0]
            if field in ["gender", "age", "muscle", "weight"]:
                meta[field] = float(lineData[1])
        f.close()
        
        return meta

class LoadTaskView(gui3d.TaskView):

    def __init__(self, category):

        gui3d.TaskView.__init__(self, category, 'Load')

        self.modelPath = None

        self.fileentry = self.addTopWidget(gui.FileEntryView('Browse', mode='dir'))
        self.fileentry.filter = 'MakeHuman Models (*.mhm)'

        @self.fileentry.mhEvent
        def onFileSelected(event):
            self.filechooser.setPaths([event.path])
            self.filechooser.refresh()

        self.filechooser = fc.IconListFileChooser(mh.getPath("models"), 'mhm', 'thumb', mh.getSysDataPath('notfound.thumb'), sort=HumanFileSort())
        self.addRightWidget(self.filechooser)
        self.addLeftWidget(self.filechooser.createSortBox())

        @self.filechooser.mhEvent
        def onFileSelected(filename):
            if gui3d.app.currentFile.modified:
                gui3d.app.prompt("Load", "You have unsaved changes. Are you sure you want to close the current file?",
                    "Yes", "No", lambda: gui3d.app.loadHumanMHM(filename))
            else:
                gui3d.app.loadHumanMHM(filename)

    def onShow(self, event):
        gui3d.TaskView.onShow(self, event)

        self.modelPath = gui3d.app.currentFile.dir
        if self.modelPath is None:
            self.modelPath = mh.getPath("models")

        self.fileentry.directory = self.modelPath
        self.filechooser.setPaths(self.modelPath)
        self.filechooser.setFocus()

        # HACK: otherwise the toolbar background disappears for some weird reason
        mh.redraw()
