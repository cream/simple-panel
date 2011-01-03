import sys
import os
import imp
import gobject
import gtk
import cairo
import rsvg
import wnck
import json

import tempfile
import time

import cream
import cream.manifest
import cream.gui

import simplepanel.applet

FADE_DURATION = 500

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

        ctx.scale(1680 / 10, 1)

        shadow_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        shadow_ctx = cairo.Context(shadow_surface)

        shadow = rsvg.Handle('data/themes/default/shadow.svg')
        shadow.render_cairo(shadow_ctx)

        background_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size()[0], self.get_size()[1])
        background_ctx = cairo.Context(background_surface)

        background = rsvg.Handle('data/themes/default/background.svg')
        background.render_cairo(background_ctx)

        ctx.set_source_surface(shadow_surface)
        ctx.paint_with_alpha(self.get_alpha()[1])

        ctx.set_source_surface(background_surface)
        ctx.paint_with_alpha(self.get_alpha()[0])


class Panel(cream.Module):

    def __init__(self):

        cream.Module.__init__(self, 'org.cream.Panel')

        applets_dir = os.path.join(self.context.get_path(), 'data/applets')
        self.applets = cream.manifest.ManifestDB(applets_dir, 'org.cream.simplepanel.Applet')
        self.layout = json.load(open('applets.json'))

        self.screen = wnck.screen_get_default()
        self.screen.connect('viewports-changed', self.viewports_changed_cb)

        self.window = PanelWindow()
        self.window.show_all()

        self.window.connect('expose-event', self.expose_cb)
        self.window.connect('button-release-event', self.click_cb)

        self.item_add = gtk.ImageMenuItem(gtk.STOCK_ADD)
        self.item_add.get_children()[0].set_label('Add applet')
        self.item_add.connect('activate', self.add_applet)

        self.menu = gtk.Menu()
        self.menu.append(self.item_add)
        self.menu.show_all()

        gobject.timeout_add(200, self.handle_fullscreen_windows)

        self.load_applets()


    def load_applets(self):

        for group_n, group in enumerate(self.layout['layout']):
            for obj_n, obj in enumerate(group['objects']):
                if obj['type'] == 'applet':
                    applet_class = self.load_applet(obj['id'])
                    applet = applet_class()
                    self.layout['layout'][group_n]['objects'][obj_n]['instance'] = applet

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
        pass


    def relayout(self):

        position = 0

        for group_n, group in enumerate(self.layout['layout']):
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
                    elif orientation == 'left':
                        position += applet.get_allocation()[0]

                    applet.set_position(position, 0)
                elif obj['type'] == 'space':
                    if orientation == 'right':
                        position -= obj['size']
                    elif orientation == 'left':
                        position += obj['size']

        self.window.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, self.window.get_size()[0],self.window.get_size()[1]), True)


    def get_applet_at_coords(self, x, y):

        for group_n, group in enumerate(self.layout['layout']):
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
        if applet is None:
            return

        x = event.x - applet.get_position()[0]
        y = event.y - applet.get_position()[1]
        applet.emit('click', x, y)


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

        for group_n, group in enumerate(self.layout['layout']):
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
