from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from .ui.dock import AgentDock


DOCK_AREA_KEY = "mapsuke/dock_area"
DOCK_AREAS = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
              Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea)
DOCK_WIDTH = 420


def area_code(area):
    # Qt 5 enums are ints; Qt 6 enums are Python enums with a value.
    return int(getattr(area, "value", area))


def saved_dock_area():
    """The area the user moved the dock to, or None if they never did."""
    value = QSettings().value(DOCK_AREA_KEY, None)
    for area in DOCK_AREAS:
        if str(value) == str(area_code(area)):
            return area
    return None


class MapsukePlugin:
    def __init__(self, iface, session_path=None):
        self.iface = iface
        self.session_path = session_path
        self.dock = None
        self.action = None
        self.processing_provider = None

    def initGui(self):
        from .core.processing_provider import AgentProcessingProvider
        if self.processing_provider is None:
            provider = AgentProcessingProvider()
            if QgsApplication.processingRegistry().addProvider(provider):
                self.processing_provider = provider
        icon = QIcon(str(Path(__file__).resolve().parent / "icon" / "icon.png"))
        self.action = QAction(icon, "Mapsuke", self.iface.mainWindow())
        self.action.triggered.connect(self.show)
        self.iface.addPluginToMenu("Mapsuke", self.action)
        self.iface.addToolBarIcon(self.action)
        # Open on first enable, then follow whether the user left the dock open.
        if QSettings().value("mapsuke/dock_open", True, type=bool):
            self.show()

    def show(self):
        if self.dock is None:
            self.dock = AgentDock(self.iface, self.session_path)
            self.place_dock()
            self.dock.toggleViewAction().toggled.connect(self.remember_dock_open)
            # Connected after the first placement, so only the user's own moves are remembered.
            self.dock.dockLocationChanged.connect(self.remember_dock_area)
        self.dock.show()
        self.dock.raise_()
        # The toggle signal needs a visible main window, which startup does not have yet.
        self.remember_dock_open(True)

    def place_dock(self):
        """Open at the right, tabbed with the side panels, unless the user placed it elsewhere.

        Tabbing joins the area of the panel it targets, and a stale saved layout can leave that
        panel in a top or bottom strip, where the dock would be a thin bar over the menu bar.
        """
        window = self.iface.mainWindow()
        right = Qt.DockWidgetArea.RightDockWidgetArea
        chosen = saved_dock_area()
        if chosen is not None and chosen != right:
            self.iface.addDockWidget(chosen, self.dock)
            return
        self.iface.addTabifiedDockWidget(right, self.dock, ["LayerStyling", "ProcessingToolbox"], True)
        if window.dockWidgetArea(self.dock) != right:
            # Tabbing pulled it out of the right side; dock it there on its own.
            self.iface.addDockWidget(right, self.dock)
            window.resizeDocks([self.dock], [DOCK_WIDTH], Qt.Orientation.Horizontal)

    def remember_dock_area(self, area):
        if area in DOCK_AREAS:
            QSettings().setValue(DOCK_AREA_KEY, area_code(area))

    def remember_dock_open(self, visible):
        QSettings().setValue("mapsuke/dock_open", visible)

    def unload(self):
        if self.processing_provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.processing_provider)
            self.processing_provider = None
        if self.dock is not None:
            # Removing the dock hides it; that must not count as the user closing it.
            self.dock.toggleViewAction().toggled.disconnect(self.remember_dock_open)
            self.dock.shutdown()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu("Mapsuke", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
