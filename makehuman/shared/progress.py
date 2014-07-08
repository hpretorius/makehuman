#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
Definition of Progress class.

**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Thanasis Papoutsidakis

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

The Progress module defines the Progress class, which provides
an easy interface for handling MH's progress bar.
It automatically processes porgress updates in subroutines, so
passing progress callbacks as function parameters is needless.

*-- Usage --*

from progress import Progress


# Standard usage.

def foo():
    progress = Progress()

    ... # do stuff #
    progress(0.7)
    ... # more stuff #
    progress(1.0)


# Usage in steps.

def bar():
    progress = Progress(42)

    ... # step 1 #
    progress.step()
    ... # step 2 #
    progress.step()
    ....
    ....
    ... # step 42 #
    progress.step()


# Usage in loops.

def baz(items):
    progress = Progress(len(items))

    for item in items:
        loopprog = Progress()
        ... # do stuff #
        loopprog(0.3)
        ... # more stuff #
        loopprog(0.6)
        ... # even more stuff #
        progress.step()


# All together!!!

def FooBarBaz():
    progress = Progress.begin()

    progress(0, 0.3, "Getting some foo")
    somefoo = foo()

    progress(0.3, 0.7, None)
    prog2 = Progress() (0, 0.5, "Getting a bar")
    bar1 = bar()
    prog2(0.5, 1, "Getting another bar")
    bar2 = bar()

    progress(0.7, 0.99, "Bazzing them all together")
    bazzable = [somefoo, bar1, bar2]
    baz(bazzable)

    progress(1.0, None, "Foobar bazzed.")

"""


global current_Progress_
current_Progress_ = None


class Progress(object):
    def __init__(self, steps=0, progressCallback=True, logging=False, timing=False):
        global current_Progress_

        self.progress = 0.0
        self.nextprog = None
        self.steps = steps
        self.stepsdone = 0
        self.description = None
        self.args = []

        self.time = None
        self.totalTime = 0.0

        self.logging = logging
        self.timing = timing

        # Push self in the global Progress object stack.
        self.parent = current_Progress_
        current_Progress_ = self

        # If this is a master Progress, get the callback
        # that updates MH's progress bar.
        if self.parent is None:
            if progressCallback is True:
                from core import G
                self.progressCallback = G.app.progress
            else:
                # Bypass importing if the user provided us
                # with a custom progress callback.
                self.progressCallback = progressCallback
            # To completely disable updating when this is a
            # master Progress, pass None as progressCallback.

    def update(self, prog=None, desc=None, *args):
        '''Internal method that is responsible for the
        actual progress bar updating.'''

        if self.steps:
            prog = float(self.stepsdone) / float(self.steps)
        if prog is None:
            prog = self.progress

        if not desc:
            if self.description:
                desc = self.description
                args = self.args
            else:
                desc = ""
                args = []

        if self.parent is None:
            if self.timing:
                import time
                t = time.time()
                if self.time:
                    deltaT = (t - self.time)
                    self.totalTime += deltaT
                    if self.logging:
                        import log
                        log.debug("  took %.4f seconds", deltaT)
                self.time = t

            if self.logging:
                import log
                log.debug("Progress %.2f%%: %s", prog, desc)  # TODO: Format desc with args

            if self.progressCallback is not None:
                self.progressCallback(prog, desc, *args)

        if prog >= 0.999999:  # Not using 1.0 for precision safety.
            self.finish()

        if self.parent:
            self.parent.childupdate(prog, desc, *args)

    def childupdate(self, prog, desc, *args):
        '''Internal method that a child Progress calls for doing a
        progress update by communicating with its parent.'''

        if self.steps:
            prog = (self.stepsdone + prog) / float(self.steps)
        elif not self.nextprog is None:
            prog = self.progress + prog * (self.nextprog - self.progress)
        else:
            prog = self.progress

        self.update(prog, desc, *args)

    def finish(self):
        '''Method to be called when a subroutine has finished,
        either explicitly (by the user), or implicitly
        (automatically when progress reaches 1.0).'''

        global current_Progress_

        if self.parent is None and self.logging and self.timing:
            import log
            log.debug("Total time taken: %s seconds.", self.totalTime)

        current_Progress_ = self.parent

    def __call__(self, progress, end=None, desc=False, *args):
        '''Basic method for progress updating.
        It overloads the () operator of the constructed object.
        Pass None to the description to allow the child update status.'''

        global current_Progress_
        current_Progress_ = self

        if not (desc is False):
            self.description = desc
            self.args = args

        self.progress = progress
        self.nextprog = end
        self.update()

        return self

    def step(self, desc=False, *args):
        '''Method useful for smaller tasks that take a number
        of roughly equivalent steps to complete.
        You can use this in a non-stepped Progress to just
        update the description on the status bar.'''

        global current_Progress_
        current_Progress_ = self

        if not (desc is False):
            self.description = desc
            self.args = args

        if self.steps:
            self.stepsdone += 1

        self.update()

        return self

    @classmethod
    def begin(cls, steps=0, progressCallback=True, logging=False, timing=False):
        '''Class method for directly creating a master Progress object.
        Resets all progress to zero. Use this for starting a greater MH task.'''

        global current_Progress_
        current_Progress_ = None

        return cls(steps, progressCallback, logging, timing)

    ## Specialized methods follow ##

    def HighFrequency(self, interval):
        '''Method that prepares the Progress object to run in a hispeed loop
        with high number of repetitions, which needs to progress the bar
        while looping without adding callback overhead.
        WARNING: ALWAYS test the overhead. Don't use this
        in extremely fast loops or it might slow them down.'''

        # Loop number interval between progress updates.
        self.HFI = interval

        # Replace original step method with the high frequency step.
        self.dostep = self.step
        self.step = self.HFstep

        return self

    def HFstep(self):
        '''Replacement method to be called in a hispeed loop instead of step().
        It is replaced internally on HighFrequency() (call step() to use it).'''

        if self.stepsdone % self.HFI > 0 and self.stepsdone < self.steps - 1:
            self.stepsdone += 1
        else:
            self.dostep()
