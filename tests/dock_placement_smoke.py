"""Where the dock opens: right side by default, never a strip in the top area, user choice kept."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
auth_dir = tempfile.TemporaryDirectory()
os.environ["QGIS_AUTH_DB_DIR_PATH"] = auth_dir.name
# Keep bundled skill installation out of the real CLI folders.
cli_homes = tempfile.TemporaryDirectory()
os.environ["CLAUDE_CONFIG_DIR"] = str(Path(cli_homes.name) / "claude")
os.environ["CODEX_HOME"] = str(Path(cli_homes.name) / "codex")
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QDockWidget, QMainWindow, QMessageBox, QTextEdit

ROOT = Path(__file__).resolve().parents[1]
import qgis
sys.path.insert(0, str(Path(qgis.__file__).resolve().parents[1] / "plugins"))
spec = importlib.util.spec_from_file_location("mapsuke_dock_test", ROOT / "__init__.py",
                                              submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
app = QgsApplication([], False)
app.initQgis()
sys.path.insert(0, str(Path(QgsApplication.pkgDataPath()) / "python/plugins"))
app.setOrganizationName("MapsukeTests")
app.setApplicationName("DockPlacement")
settings_dir = tempfile.TemporaryDirectory()
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir.name)
QSettings().setValue("mapsuke/executable", sys.executable)
QSettings().setValue("mapsuke/codex_executable", sys.executable)
from mapsuke_dock_test.plugin import DOCK_AREA_KEY, MapsukePlugin

RIGHT, LEFT, TOP = (Qt.DockWidgetArea.RightDockWidgetArea, Qt.DockWidgetArea.LeftDockWidgetArea,
                    Qt.DockWidgetArea.TopDockWidgetArea)


class Canvas:
    def refresh(self):
        pass


class Iface:
    """A QMainWindow with the panels Mapsuke tabs with. Like QGIS, tabbing joins the target's area."""
    def __init__(self, panel_area=RIGHT):
        self.window = QMainWindow()
        self.window.setCentralWidget(QTextEdit())
        self.window.resize(1200, 800)
        self.panels = {}
        for name in ("LayerStyling", "ProcessingToolbox"):
            panel = QDockWidget(name)
            panel.setObjectName(name)
            panel.setWidget(QTextEdit())
            self.window.addDockWidget(panel_area, panel)
            self.panels[name] = panel
        self.actions = []

    def mainWindow(self):
        return self.window

    def activeLayer(self):
        return None

    def mapCanvas(self):
        return Canvas()

    def addPluginToMenu(self, menu, action):
        self.actions.append(action)

    def addToolBarIcon(self, action):
        pass

    def addDockWidget(self, area, dock):
        self.window.addDockWidget(area, dock)

    def addTabifiedDockWidget(self, area, dock, tabify_with, raise_tab):
        self.window.addDockWidget(area, dock)
        for name in tabify_with:
            if name in self.panels:
                self.window.tabifyDockWidget(self.panels[name], dock)
                break

    def removeDockWidget(self, dock):
        self.window.removeDockWidget(dock)

    def removePluginMenu(self, menu, action):
        self.actions.remove(action)

    def removeToolBarIcon(self, action):
        pass


def open_plugin(iface):
    plugin = MapsukePlugin(iface, Path(settings_dir.name) / "sessions.sqlite3")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        plugin.initGui()
    iface.window.show()
    app.processEvents()
    return plugin


# First open: right side, tabbed with the panels there, with room to read.
iface = Iface()
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == RIGHT
assert iface.window.tabifiedDockWidgets(iface.panels["LayerStyling"]).count(plugin.dock) == 1
assert plugin.dock.minimumHeight() >= 200 and plugin.dock.minimumWidth() >= 200
assert not QSettings().contains(DOCK_AREA_KEY), "placing the dock is not a user choice"
plugin.unload()
iface.window.close()

# The panels sit in the top area (stale saved layout): tabbing would carry the dock there.
iface = Iface(panel_area=TOP)
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == RIGHT
assert plugin.dock.height() >= plugin.dock.minimumHeight()
assert not QSettings().contains(DOCK_AREA_KEY)
# Moving the dock is remembered and respected on the next start, even next to top-area panels.
iface.window.addDockWidget(LEFT, plugin.dock)
app.processEvents()
assert QSettings().value(DOCK_AREA_KEY, type=int) == 1
plugin.unload()
iface.window.close()
iface = Iface(panel_area=TOP)
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == LEFT
# A deliberate move to the top area is kept too, now with a usable minimum height.
iface.window.addDockWidget(TOP, plugin.dock)
app.processEvents()
plugin.unload()
iface.window.close()
iface = Iface()
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == TOP
assert plugin.dock.height() >= plugin.dock.minimumHeight()
# Moving back to the right restores the default behavior.
iface.window.addDockWidget(RIGHT, plugin.dock)
app.processEvents()
plugin.unload()
iface.window.close()
iface = Iface(panel_area=TOP)
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == RIGHT
plugin.unload()
iface.window.close()
# An unusable saved value is ignored.
QSettings().setValue(DOCK_AREA_KEY, "garbage")
iface = Iface(panel_area=TOP)
plugin = open_plugin(iface)
assert iface.window.dockWidgetArea(plugin.dock) == RIGHT
plugin.unload()
iface.window.close()
print("dock placement smoke test passed")
