import gobject
import gtk
import cairo
import re
import thread

import simplepanel.applet

from cream.util.subprocess import Subprocess
from cream.xdg.desktopentries import DesktopEntry

from bubble import Bubble
from menuitem import MenuItem

PADDING = 5
KICK = re.compile('%[ifFuUck]')

CATEGORY_ICONS = {
        "AudioVideo": 'applications-multimedia',
        "Audio": 'applications-multimedia',
        "Video": 'applications-multimedia',
        "Development": 'applications-development',
        "Education": 'applications-science',
        "Game": 'applications-games',
        "Graphics": 'applications-graphics',
        "Network": 'applications-internet',
        "Office": 'applications-office',
        "Settings": 'applications-engineering',
        "System": 'applications-system',
        "Utility": 'applications-other',
    }

CATEGORIES = ['Network', 'Graphics', 'Office', 'Development', 'Audio', 'Game', 'Utility', 'System', 'Settings']

class Category(gobject.GObject):

    __gtype_name__ = 'Category'
    __gsignals__ = {
        'hide': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }

    def __init__(self, id_, base_path):

        gobject.GObject.__init__(self)

        self.id = id_

        self.bubble = Bubble(base_path)

        self.layout = gtk.VBox()
        self.layout.set_spacing(2)
        self.layout.show_all()

        self.bubble.add(self.layout)

        self.bubble.window.connect('button-press-event', self.bubble_button_press_cb)


    def show(self, x, y):

        self.bubble.show(x, y)
        while gtk.events_pending():
            gtk.main_iteration()
        gtk.gdk.pointer_grab(self.bubble.window.window, owner_events=True, event_mask=self.bubble.window.get_events() | gtk.gdk.BUTTON_PRESS_MASK)


    def hide(self):

        gtk.gdk.pointer_ungrab()
        self.bubble.hide()
        self.emit('hide')


    def bubble_button_press_cb(self, source, event):

        if event.x <= self.bubble.window.allocation.x\
            or event.y <= self.bubble.window.allocation.y\
            or event.x >= self.bubble.window.allocation.x + self.bubble.window.allocation.width\
            or event.y >= self.bubble.window.allocation.y + self.bubble.window.allocation.height:
                gtk.gdk.pointer_ungrab()
                self.bubble.hide()
                self.emit('hide')


    def add_item(self, desktop_entry):

        if desktop_entry.has_option_default('NoDisplay') and desktop_entry.no_display:
            return

        item = MenuItem(desktop_entry)
        item.connect('button-release-event', self.button_release_cb)
        item.show()
        self.layout.pack_start(item, False, True)


    def button_release_cb(self, source, event):

        self.bubble.hide()
        self.emit('hide')

        exec_ = KICK.sub('', source.desktop_entry.exec_)

        Subprocess([exec_.strip()]).run()


@simplepanel.applet.register
class MenuApplet(simplepanel.applet.Applet):

    def __init__(self):
        simplepanel.applet.Applet.__init__(self)

        self.default_size = 22
        self.padding = 5

        self._active_menu = None

        self.connect('click', self.click_cb)

        self.categories = []

        for cat in CATEGORIES:
            category = Category(cat, self.context.get_path())
            category.connect('hide', self.menu_hide_cb)
            self.categories.append(category)

        thread.start_new_thread(self.fill_categories, ())


    def fill_categories(self):
        for desktop_entry in DesktopEntry.get_all():
            for category in self.categories:
                if category.id in desktop_entry.categories:
                    category.add_item(desktop_entry)

    def menu_hide_cb(self, source):

        if self._active_menu == source:
            self._active_menu = None


    def get_category_at_coords(self, x, y):

        for c, category in enumerate(self.categories):
            w = h = self.default_size
            x0, y0 = PADDING + c * (w + PADDING), 1
            x1, y1 = x0 + w, y0 + h
            if x >= x0 and x <= x1 and y >= y0 and y <= y1:
                return (category, x0, x1-x0)

        return (None, None, None)


    def click_cb(self, applet, x, y):

        category, position, width = self.get_category_at_coords(x, y)
        if not category:
            return

        if self._active_menu:
            self._active_menu.hide()
        category.show(position + width/2, y)
        self._active_menu = category


    def get_size(self):

        allocation = self.get_allocation()
        if allocation is not None:
            return allocation[1]
        else:
            return self.default_size


    def render(self, ctx):

        position = PADDING

        for category in self.categories:
            icon_name = CATEGORY_ICONS[category.id]
            theme = gtk.icon_theme_get_default()
            icon_info = theme.lookup_icon(icon_name, 22, 0)
            pb = gtk.gdk.pixbuf_new_from_file(icon_info.get_filename())
            pb = pb.scale_simple(22, 22, gtk.gdk.INTERP_HYPER)

            width = height = 22

            ctx.set_source_pixbuf(pb, position, (self.get_allocation()[1] - height) / 2)
            ctx.paint()

            position += width + self.padding


    def allocate(self, height):

        width = PADDING

        for category in self.categories:
            width += self.get_size() + PADDING

        self.set_allocation(width, height)

        return self.get_allocation()
