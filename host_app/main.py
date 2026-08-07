#!/usr/bin/env python3
import sys
import os

# Ensure host_app directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from gui_main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PopRoaster App")
    app.setOrganizationName("PopRoaster")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
