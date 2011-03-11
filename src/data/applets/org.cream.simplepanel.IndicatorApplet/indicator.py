from cream.util.dicts import ordereddict

import ctypes
import sys

# Wrap gobject...
import gobject

class _PyGObject_Functions(ctypes.Structure):
    _fields_ = [
        ('register_class',
         ctypes.PYFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p,
                           ctypes.c_int, ctypes.py_object,
                           ctypes.py_object)),
        ('register_wrapper',
         ctypes.PYFUNCTYPE(ctypes.c_void_p, ctypes.py_object)),
        ('register_sinkfunc',
         ctypes.PYFUNCTYPE(ctypes.py_object, ctypes.c_void_p)),
        ('lookupclass',
         ctypes.PYFUNCTYPE(ctypes.py_object, ctypes.c_int)),
        ('newgobj',
         ctypes.PYFUNCTYPE(ctypes.py_object, ctypes.c_void_p)),
        ]

class PyGObjectCPAI(object):
    def __init__(self):
        PyCObject_AsVoidPtr = ctypes.pythonapi.PyCObject_AsVoidPtr
        PyCObject_AsVoidPtr.restype = ctypes.c_void_p
        PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
        addr = PyCObject_AsVoidPtr(ctypes.py_object(
            gobject._PyGObject_API))
        self._api = _PyGObject_Functions.from_address(addr)

    def pygobject_new(self, addr):
        return self._api.newgobj(addr)

capi = PyGObjectCPAI()

glib = ctypes.CDLL('libglib-2.0.so.0')

def glist(addr):
    class _GList(ctypes.Structure):
        _fields_ = [('data', ctypes.c_void_p),
                    ('next', ctypes.c_void_p)]
    l = addr
    while l:
        l = _GList.from_address(l)
        yield l.data
        l = l.next


# Wrap libindicator...
libindicator = ctypes.CDLL('/usr/lib/libindicator.so')
indicator_object_new_from_file = libindicator.indicator_object_new_from_file
indicator_object_get_entries = libindicator.indicator_object_get_entries


class _IndicatorObjectEntry(ctypes.Structure):
    _fields_ = [
        ("label", ctypes.c_int),
        ("image", ctypes.c_int),
        ("menu", ctypes.c_int)]


class IndicatorObjectEntry(object):

    def __init__(self, label, pixbuf, menu):

        self.label = label
        self.pixbuf = pixbuf
        self.menu = menu


    @classmethod
    def from_address(cls, addr):

        _entry = _IndicatorObjectEntry.from_address(addr)

        if _entry.label:
            label = capi.pygobject_new(_entry.label).get_label()
        else:
            label = None

        if _entry.image:
            pixbuf = capi.pygobject_new(_entry.image).get_pixbuf()
        else:
            pixbuf = None

        if _entry.menu:
            menu = capi.pygobject_new(_entry.menu)
        else:
            menu = None

        return cls(label, pixbuf, menu)


class IndicatorObject(gobject.GObject):

    #__gtype_name__ = 'IndicatorObject'
    __gsignals__ = {
        'entry-added': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'entry-removed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        }

    def __init__(self, path):

        gobject.GObject.__init__(self)

        self.path = path

        self.address = indicator_object_new_from_file(path)
        self.indicator = capi.pygobject_new(self.address)

        self.indicator.connect('entry-added', self.entry_added_cb)
        self.indicator.connect('entry-removed', self.entry_removed_cb)

        self.entries = ordereddict()

        _entries = glist(indicator_object_get_entries(self.address))
        for _entry in _entries:
            self.entries[_entry] = IndicatorObjectEntry.from_address(_entry)


    def get_entries(self):
        return self.entries.values()


    def entry_added_cb(self, indicator, _entry):

        addr = int(str(_entry)[13:-1],16)
        entry = IndicatorObjectEntry.from_address(addr)
        self.entries[addr] = entry

        self.emit('entry-added', entry)


    def entry_removed_cb(self, indicator, _entry):

        addr = int(str(_entry)[13:-1],16)
        entry = IndicatorObjectEntry.from_address(addr)

        del self.entries[addr]

        self.emit('entry-removed', entry)


gobject.type_register(IndicatorObject)
