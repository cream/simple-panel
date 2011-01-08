#!/usr/bin/env python
import gobject
import gtk
import cairo
from appindicators.host import StatusNotifierHost, Status

import simplepanel.applet

FONT = ('Droid Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
FONT_SIZE = 14
COLOR = (.1, .1, .1, 1)
PADDING = 5


class Indicator(object):

    def __init__(self, item, applet):

        self.item = item
        self.applet = applet

        self.status = None
        self.icons = {}

        item.connect('icon-new', lambda *x: applet.emit('render-request'))
        item.connect('attention-icon-new', lambda *x: applet.emit('render-request'))
        item.connect('status-new', lambda *x: applet.emit('render-request'))


    @property
    def icon_name(self):
        if self.item.status == Status.NeedsAttention:
            return self.item.attention_icon_name
        else:
            return self.item.icon_name


    def lookup_icon(self, size):

        icon_name = self.icon_name
        if icon_name in self.icons:
            return self.icons[icon_name]

        theme = gtk.icon_theme_get_default()
        if self.item.icon_theme_path:
            theme.append_search_path(self.item.icon_theme_path)

        icon_info = theme.lookup_icon(icon_name, size, 0)
        if icon_info is None:
            raise ValueError('Icon wasn\'t found! %r' % self.icon_name)

        self.icons[icon_name] = icon_info.get_filename()
        return self.icons[icon_name]


    def get_icon_path(self, size):

        if self.item.status == self.status:
            return self.lookup_icon(size)
        else:
            self.status = self.item.status
            return self.lookup_icon(size)



@simplepanel.applet.register
class ApplicationIndicatorApplet(simplepanel.applet.Applet):

    def __init__(self):
        simplepanel.applet.Applet.__init__(self)

        self.default_size = 22
        self.padding = 5

        self.host = StatusNotifierHost()
        self.host.connect('item-added', self.item_added_cb)
        self.host.connect('item-removed', self.item_added_cb)
        self.indicators = [Indicator(item, self) for item in self.host.items]

        self.connect('click', self.click_cb)


    def item_added_cb(self, host, item):
        self.indicators = [Indicator(item, self) for item in self.host.items]
        self.allocate(self.get_allocation()[1])
        self.draw()


    def item_removed_cb(self, host, item):
        self.indicators = [Indicator(item, self) for item in self.host.items]
        self.allocate(self.get_allocation()[1])
        self.draw()


    def get_indicator_at_coords(self, x, y):

        for c, indicator in enumerate(self.indicators):
            w = h = self.default_size
            x0, y0 = PADDING + c * (w + PADDING), 1
            x1, y1 = x0 + w, y0 + h
            if x >= x0 and x <= x1 and y >= y0 and y <= y1:
                return indicator
        return None


    def click_cb(self, applet, x, y):

        indicator = self.get_indicator_at_coords(x, y)
        if indicator:
            menu = indicator.item.dbusmenu_gtk.root_widget
            menu.popup(None, None, None, 1, 0)
            win = menu.get_parent()
            x, y = win.get_position()
            win.move(x, self.get_allocation()[1] + 1)


    def get_size(self):

        allocation = self.get_allocation()
        if allocation is not None:
            return allocation[1]
        else:
            return self.default_size


    def render(self, ctx):

        position = PADDING

        for indicator in self.indicators:
            icon_path = indicator.get_icon_path(self.get_size())

            icon = gtk.gdk.pixbuf_new_from_file_at_size(icon_path, self.get_size(), self.get_size())

            icon_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.get_size(), self.get_size())
            icon_context = gtk.gdk.CairoContext(cairo.Context(icon_surface))
            icon_context.set_source_pixbuf(icon, 0, 0)
            icon_context.paint()

            height = icon_surface.get_height()
            width = icon_surface.get_width()

            ctx.set_source_surface(icon_surface, position, (self.get_allocation()[1] - height) / 2)
            ctx.paint()

            position += width + self.padding


    def allocate(self, height):

        width = PADDING

        for indicator in self.indicators:
            width += self.get_size() + PADDING

        self.set_allocation(width, height)

        return self.get_allocation()
