"""Offscreen Qt smoke tests for MainWindow."""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestMainWindowSmoke(unittest.TestCase):
    """Smoke tests for MainWindow with offscreen Qt platform."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication once for all tests."""
        from PySide6 import QtWidgets, QtCore

        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication(sys.argv)

    def test_instantiate_from_pyplayer_ui(self):
        """Test MainWindow from src.pyplayer.ui.main_window instantiates."""
        from src.pyplayer.ui.main_window import MainWindow

        window = MainWindow()
        self.assertIsNotNone(window)

        self.assertTrue(hasattr(window, "menuBar"))
        self.assertTrue(callable(window.menuBar))

        self.assertTrue(hasattr(window, "centralWidget"))
        self.assertTrue(callable(window.centralWidget))

        self.assertTrue(hasattr(window, "dock_widget"))

        self.assertTrue(hasattr(window, "statusBar"))
        self.assertTrue(callable(window.statusBar))

        window.close()
        del window

    def test_instantiate_from_main_python_ui(self):
        """Test MainWindow from src.main.python.ui.main_window instantiates."""
        from src.main.python.ui.main_window import MainWindow

        window = MainWindow()
        self.assertIsNotNone(window)

        self.assertTrue(hasattr(window, "menuBar"))
        self.assertTrue(callable(window.menuBar))

        self.assertTrue(hasattr(window, "centralWidget"))
        self.assertTrue(callable(window.centralWidget))

        self.assertTrue(hasattr(window, "dock_widget"))

        self.assertTrue(hasattr(window, "statusBar"))
        self.assertTrue(callable(window.statusBar))

        window.close()
        del window

    def test_menuBar_exists(self):
        """Test menuBar() returns a widget."""
        from src.pyplayer.ui.main_window import MainWindow

        window = MainWindow()
        menu_bar = window.menuBar()
        self.assertIsNotNone(menu_bar)
        self.assertTrue(hasattr(menu_bar, "actions"))
        window.close()
        del window

    def test_centralWidget_exists(self):
        """Test centralWidget() returns a widget."""
        from src.pyplayer.ui.main_window import MainWindow

        window = MainWindow()
        central = window.centralWidget()
        self.assertIsNotNone(central)
        window.close()
        del window

    def test_dock_widget_exists(self):
        """Test dock_widget attribute exists."""
        from src.pyplayer.ui.main_window import MainWindow

        window = MainWindow()
        self.assertTrue(hasattr(window, "dock_widget"))
        self.assertIsNotNone(window.dock_widget)
        window.close()
        del window

    def test_statusBar_exists(self):
        """Test statusBar() returns a widget."""
        from src.pyplayer.ui.main_window import MainWindow

        window = MainWindow()
        status_bar = window.statusBar()
        self.assertIsNotNone(status_bar)
        window.close()
        del window


if __name__ == "__main__":
    unittest.main()