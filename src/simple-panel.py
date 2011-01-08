#! /usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import sys
import os
import imp
import gobject
import gtk
import cairo
import wnck
import json

import tempfile
import time
from operator import itemgetter

import cream
import cream.manifest
import cream.gui
import cream.gui.svg

import simplepanel.applet
from simplepanel.dialog import AddAppletDialog

FADE_DURATION = 500
MOUSE_BUTTON_RIGHT = 3

def copy_layout(layout):
    l = []

    for group in layout:
        g = {}
        g['orientation'] = group['orientation']
        g['position'] = group['position']
        g['objects'] = []

        for obj in group['objects']:
            o = {}
            o['type'] = obj['type']

            if obj['type'] == 'applet':
                o['id'] = obj['id']
            else:
                o['size'] = obj['size']
           
            g['objects'].append(o)

        l.append(g)

    return l


class PanelWindow(gtk.Window):

    def __init__(self):

        gtk.Window.__init__(self)

        self._alpha = (.5, 1)

        # Setting up the Widget's window...
        self.stick()
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DOCK)
        self.set_keep_above(True)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_resizable(False)
        self.set_colormap(self.get_screen().get_rgba_colormap())

        self.display = self.get_display()
        self.screen = self.display.get_default_screen()
        width, height = self.screen.get_width(), self.screen.get_height()

        self.set_size_request(width, 40)

        self.connect('expose-event', self.expose_cb)
        self.connect('realize', self.realize_cb)
        
        # Draw the background…
        self.background_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        background_ctx = cairo.Context(self.background_surface)

        background = cream.gui.svg.Handle('data/themes/default/background.svg')
        background.dom.getElementById('stretch').setAttribute('width', str(1440))
        background.dom.getElementById('stretch').setAttribute('height', str(24))
        background.save_dom()
        background.render_cairo(background_ctx)

        # … and the shadow…
        self.shadow_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        shadow_ctx = cairo.Context(self.shadow_surface)
        shadow_ctx.translate(0, 23)
        shadow = cream.gui.svg.Handle('data/themes/default/shadow.svg')
        shadow.dom.getElementById('shadow').setAttribute('width', str(1440))
        #shadow.dom.getElementById('border').setAttribute('width', str(1440))
        shadow.save_dom()
        shadow.render_cairo(shadow_ctx)

        # … and the border.
        self.border_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        border_ctx = cairo.Context(self.border_surface)
        border_ctx.translate(0, 23)
        border = cream.gui.svg.Handle('data/themes/default/border.svg')
        border.dom.getElementById('border').setAttribute('width', str(1440))
        border.save_dom()
        border.render_cairo(border_ctx)


    def set_alpha(self, bg, sdw):
        self._alpha = (bg, sdw)


    def get_alpha(self):
        return self._alpha


    def realize_cb(self, window):
        self.window.set_events(self.window.get_events() | gtk.gdk.BUTTON_RELEASE_MASK)
        self.window.property_change("_NET_WM_STRUT", "CARDINAL", 32, gtk.gdk.PROP_MODE_REPLACE, [0, 0, 24, 0])
        self.window.input_shape_combine_region(gtk.gdk.region_rectangle((0, 0, self.get_size()[0], 24)), 0, 0)


    def expose_cb(self, source, event):
        """ Clear the widgets background. """

        ctx = source.window.cairo_create()

        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        ctx.set_operator(cairo.OPERATOR_OVER)

        ctx.set_source_surface(self.background_surface)
        ctx.paint_with_alpha(self.get_alpha()[0])

        ctx.set_source_surface(self.shadow_surface)
        ctx.paint_with_alpha(self.get_alpha()[1])

        ctx.set_source_surface(self.border_surface)
        ctx.paint_with_alpha(100)


class Panel(cream.Module):
    """ Main class of the Panel module. """

    def __init__(self):

        cream.Module.__init__(self, 'org.cream.Panel')

        # Load themes and applets...
        applets_dir = os.path.join(self.context.get_path(), 'data/applets')
        self.applets = cream.manifest.ManifestDB(applets_dir, 'org.cream.simplepanel.Applet')
        self.layout = copy_layout(self.config.layout)
        #self.layout = json.load(open('applets.json'))

        self.screen = wnck.screen_get_default()
        self.screen.connect('viewports-changed', self.viewports_changed_cb)

        self.window = PanelWindow()
        self.window.show_all()

        self.window.connect('expose-event', self.expose_cb)
        self.window.connect('button-release-event', self.click_cb)

        self.item_add = gtk.ImageMenuItem(gtk.STOCK_ADD)
        self.item_add.get_children()[0].set_label('Add applet')
        self.item_add.connect('activate', lambda *x: self.add_applet())

        self.menu = gtk.Menu()
        self.menu.append(self.item_add)
        self.menu.show_all()

        applets = sorted(self.applets.by_id.itervalues(),key=itemgetter('name'))
        self.add_dialog = AddAppletDialog(applets)


        gobject.timeout_add(200, self.handle_fullscreen_windows)

        self.load_applets()
        
        self.save_layout()
        
        
    def save_layout(self):

        self.config.layout = copy_layout(self.layout)


    def load_applets(self):

        for group_n, group in enumerate(self.layout):
            for obj_n, obj in enumerate(group['objects']):
                if obj['type'] == 'applet':
                    applet_class = self.load_applet(obj['id'])
                    applet = applet_class()
                    self.layout[group_n]['objects'][obj_n]['instance'] = applet

                    applet.allocate(24)

                    applet.connect('render-request', self.render_request_cb)
                    applet.connect('allocation-changed', self.allocation_changed_cb)

        self.relayout()


    def load_applet(self, applet_id):

        path = self.applets.get_by_id(applet_id)['path']

        applet_file = os.path.join(path, '__init__.py')
        applet_name = applet_id.split('.')[-1]
        if os.path.isfile(applet_file):
            sys.path.insert(0, path)
            imp.load_module(
                'applet_{0}'.format(applet_name),
                open(applet_file),
                applet_file,
                ('.py', 'r', imp.PY_SOURCE)
            )
            del sys.path[0]
            applet = simplepanel.applet.APPLETS[applet_file]
            return applet
        else:
            return None


    def add_applet(self):
        self.add_dialog.dialog.show_all()

        if self.add_dialog.dialog.run() == 1:
            applet = self.add_dialog.selected_applet

        self.add_dialog.dialog.hide()


    def relayout(self):

        position = 0

        for group_n, group in enumerate(self.layout):
            orientation = group['orientation']

            if orientation == 'right':
                position = self.window.get_size()[0] - group['position']
                objects = group['objects']
                objects.reverse()
            elif orientation == 'left':
                position = group['position']
                objects = group['objects']
            for obj_n, obj in enumerate(objects):
                if obj['type'] == 'applet':
                    applet = obj['instance']
                    if orientation == 'right':
                        position -= applet.get_allocation()[0]
                        applet.set_position(position, 0)
                    elif orientation == 'left':
                        applet.set_position(position, 0)
                        position += applet.get_allocation()[0]
                elif obj['type'] == 'space':
                    if orientation == 'right':
                        position -= obj['size']
                    elif orientation == 'left':
                        position += obj['size']
            if orientation == 'right':
                objects.reverse()

        self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)


    def get_applet_at_coords(self, x, y):

        for group_n, group in enumerate(self.layout):
            orientation = group['orientation']
            position = group['position']
            for obj_n, obj in enumerate(group['objects']):
                if obj['type'] == 'applet':
                    applet = obj['instance']
                    w, h = applet.get_allocation()
                    x0, y0 = applet.get_position()
                    x1, y1 = x0 + w, y0 + h
                    if x >= x0 and x <= x1 and y >= y0 and y <= y1:
                        return applet
        return None


    def click_cb(self, window, event):
        applet = self.get_applet_at_coords(event.x, event.y)
        if applet is not None:
            x = event.x - applet.get_position()[0]
            y = event.y - applet.get_position()[1]
            applet.emit('click', x, y)
        elif event.button == MOUSE_BUTTON_RIGHT:
            self.menu.popup(None, None, None, event.button, event.get_time())


    def handle_fullscreen_windows(self):

        windows = self.screen.get_windows()
        workspace = self.screen.get_active_workspace()
        for w in windows:
            if w.is_maximized() and w.is_in_viewport(workspace):
                if self.window.get_alpha()[0] == .5:

                    def update(t, state):
                        self.window.set_alpha(.5 + state * .5, 1 - state)
                        self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)

                    t = cream.gui.Timeline(FADE_DURATION, cream.gui.CURVE_SINE)
                    t.connect('update', update)
                    t.run()
                break
        else:
            if self.window.get_alpha()[0] == 1:

                def update(t, state):
                    self.window.set_alpha(1 - state * .5, state)
                    self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)

                t = cream.gui.Timeline(FADE_DURATION, cream.gui.CURVE_SINE)
                t.connect('update', update)
                t.run()

        return True


    def viewports_changed_cb(self, screen):
        self.handle_fullscreen_windows()


    def expose_cb(self, *args):

        ctx = self.window.window.cairo_create()

        for group_n, group in enumerate(self.layout):
            orientation = group['orientation']
            position = group['position']
            for obj_n, obj in enumerate(group['objects']):
                if obj['type'] == 'applet':
                    applet = obj['instance']

                    ctx.save()
                    x, y = applet.get_position()
                    width, height = applet.get_allocation()
                    ctx.translate(x, y)
                    ctx.rectangle(0, 0, width, height)
                    ctx.clip()

                    applet.render(ctx)
                    ctx.restore()


    def render_request_cb(self, applet):

        x, y = applet.get_position()
        width, height = applet.get_allocation()

        self.window.window.invalidate_rect(gtk.gdk.Rectangle(int(x), int(y), int(width), int(height)), True)

        # What the heck? TODO: Check.
        #ctx = self.window.window.cairo_create()

        #ctx.translate(x, y)
        #ctx.rectangle(0, 0, width, height)
        #ctx.clip()
        #applet.render(ctx)


    def allocation_changed_cb(self, applet, allocation):
        self.relayout()



if __name__ == '__main__':
    panel = Panel()
    panel.main()
