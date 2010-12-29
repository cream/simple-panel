#! /usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import inspect
import os.path
import weakref
import gobject
import threading
import tempfile

APPLETS = dict()

class Applet(gobject.GObject):

    __gtype_name__ = 'Applet'
    __gsignals__ = {
        'render-request': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_PYOBJECT, ()),
        'allocation-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'allocation-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'click': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_INT)),
        }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.allocation = None
        self.position = None


    def draw(self):

        self.emit('render-request')


    def render(self, ctx):
        pass


    def set_position(self, x, y):
        self.position = (x, y)


    def get_position(self):
        return self.position


    def set_allocation(self, width, height):

        self.allocation = (width, height)
        self.emit('allocation-changed', self.get_allocation())


    def get_allocation(self):
        return self.allocation


    def allocate(self, height):
        width = 30
        self.set_allocation(width, height)
        return self.get_allocation()


def register(applet):
    """ Register the given API object. """

    def decorator(applet):
        path = os.path.abspath(inspect.getsourcefile(applet))
        APPLETS[path] = applet
        return applet

    decorator(applet)
