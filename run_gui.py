#!/usr/bin/env python3
"""
Simple GUI Launcher for SignalScan PRO
"""

if __name__ == "__main__":
    import sys
    import os
    
    # Get the absolute path to the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add to path if not already there
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    print(f"Python path: {project_dir}")
    print(f"Python version: {sys.version}")
    print(f"Looking for gui module...")
    
    # Now try importing
    try:
        from PyQt5.QtWidgets import QApplication
        print("✓ PyQt5 found")
    except ImportError as e:
        print(f"✗ PyQt5 not found: {e}")
        sys.exit(1)
    
    try:
        from core.file_manager import FileManager
        from core.logger import Logger
        print("✓ Core modules found")
    except ImportError as e:
        print(f"✗ Core modules not found: {e}")
        sys.exit(1)
    
    try:
        from gui.main_window import MainWindow
        print("✓ GUI module found")
    except ImportError as e:
        print(f"✗ GUI module not found: {e}")
        print(f"Current directory contents: {os.listdir(project_dir)}")
        print(f"GUI directory exists: {os.path.exists(os.path.join(project_dir, 'gui'))}")
        if os.path.exists(os.path.join(project_dir, 'gui')):
            print(f"GUI directory contents: {os.listdir(os.path.join(project_dir, 'gui'))}")
        sys.exit(1)
    
    # Initialize
    print("\n" + "=" * 60)
    print("Launching SignalScan PRO GUI")
    print("=" * 60)
    
    file_manager = FileManager()
    logger = Logger()
    
    app = QApplication(sys.argv)
    window = MainWindow(file_manager, logger)
    window.show()
    
    print("✓ GUI window opened!")
    
    sys.exit(app.exec_())