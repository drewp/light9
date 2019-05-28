from lib.ipython_view import IPythonView
import gi  # noqa
from gi.repository import Gtk
from gi.repository import Pango


def togglePyConsole(self, item, user_ns):
    """
    toggles a toplevel window with an ipython console inside.

    self is an object we can stick the pythonWindow attribute on

    item is a checkedmenuitem

    user_ns is a dict you want to appear as locals in the console
    """
    if item.get_active():
        if not hasattr(self, 'pythonWindow'):
            self.pythonWindow = Gtk.Window()
            S = Gtk.ScrolledWindow()
            S.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            V = IPythonView(user_ns=user_ns)
            V.modify_font(Pango.FontDescription("luxi mono 8"))
            V.set_wrap_mode(Gtk.WrapMode.CHAR)
            S.add(V)
            self.pythonWindow.add(S)
            self.pythonWindow.show_all()
            self.pythonWindow.set_size_request(750, 550)
            self.pythonWindow.set_resizable(True)

            def onDestroy(*args):
                item.set_active(False)
                del self.pythonWindow

            self.pythonWindow.connect("destroy", onDestroy)
    else:
        if hasattr(self, 'pythonWindow'):
            self.pythonWindow.destroy()
