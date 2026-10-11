#!/usr/bin/env python3
"""
RPG Database Management System - Main Application Entry Point

A desktop application for managing RPG content using a document-centric approach
for campaigns, sessions and entities.
"""

import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon

    # Import application modules
    from config.settings import Settings
    from config.version import APP_NAME, APP_VERSION, get_version_string
    from gui.main_window import MainWindow
    from models.database import DatabaseManager
    from utils.logger import setup_logging
    from utils.ui_helpers import show_error

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install the required dependencies:")
    print("pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Main application entry point."""

    # Minimal pre-QApplication console logger.
    # QStandardPaths (used by setup_logging for the log file location) requires
    # a QApplication with the correct identity to be set up first.  Calling it
    # before QApplication would let Qt cache the executable filename ("python"
    # or "RPG_Database_Manager") as the app identity, producing a different
    # AppData path for every entry point — the root cause of EXE vs Python
    # using different database files.  We therefore defer full logging setup
    # until after QApplication identity is configured.
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)s - %(name)s - %(message)s')
    pre_logger = logging.getLogger('rpg_database_manager')
    pre_logger.info(f"Starting {get_version_string()}")

    # Initialize variables that might be used in finally block
    db_manager = None
    exit_code = 1

    # Setup high DPI scaling BEFORE creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create Qt Application and set identity BEFORE any QStandardPaths call.
    # All subsequent calls to QStandardPaths (logging, database, images, etc.)
    # will resolve to the same AppData path regardless of how the app is launched.
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    app.setOrganizationDomain("rpgdb.local")

    # NOW safe to set up file logging — QStandardPaths has correct identity
    logger = setup_logging(level=logging.INFO)
    logger.info(f"Starting {get_version_string()}")

    # Set application icon if available
    icon_path = project_root / "data" / "icons" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        logger.warning(f"Application icon not found at: {icon_path}")

    # A slot that raises would otherwise abort the whole process (PyQt6 default)
    from utils.exception_hook import install as install_exception_hook
    install_exception_hook()

    # Load application settings
    try:
        settings = Settings()
        settings.load_settings()
    except Exception as e:
        logger.warning(f"Could not load settings: {e}")
        settings = Settings()

    # Leftovers of the removed AI features (provider list with the encrypted API keys)
    try:
        from config.paths import get_data_dir
        from utils.legacy_cleanup import remove_legacy_ai_data
        remove_legacy_ai_data(get_data_dir())
    except Exception as e:
        logger.warning(f"Could not clean up old AI data: {e}")

    # Apply application-wide font from settings
    try:
        from PyQt6.QtGui import QFont
        app_font = QFont(settings.ui.font_family, settings.ui.font_size)
        app.setFont(app_font)
        logger.info(f"Applied application font: {settings.ui.font_family} {settings.ui.font_size}pt")
    except Exception as e:
        logger.warning(f"Could not apply application font: {e}")

    # Initialize StyleManager with settings for typography
    try:
        from gui.theme.style_manager import get_style_manager
        get_style_manager(theme=settings.ui.theme, ui_settings=settings.ui)
        logger.info(f"Initialized StyleManager with typography scale: {settings.ui.typography_scale}")

        # Apply the theme before any window exists so the first paint is already themed
        from gui.theme import get_theme_manager
        get_theme_manager().apply(app, settings.ui.theme)
    except Exception as e:
        logger.warning(f"Could not initialize StyleManager: {e}")

    # Initialize database
    try:
        db_manager = DatabaseManager()
        db_manager.initialize_database()
    except Exception as e:
        error_msg = f"Failed to initialize database: {e}"
        logger.error(error_msg)

        # Show error dialog
        show_error(
            None,
            "Database Error",
            "Failed to initialize the application database.",
            error_msg
        )
        sys.exit(1)

    # Create and show main window
    try:
        main_window = MainWindow(settings, db_manager)
        main_window.show()

        # Start the event loop
        exit_code = app.exec()

    except Exception as e:
        error_msg = f"Failed to start application: {e}"
        logger.exception(error_msg)

        # Show error dialog
        show_error(
            None,
            "Application Error",
            "Failed to start the RPG Database Manager.",
            error_msg
        )
        exit_code = 1

    finally:
        # Cleanup database connection
        if db_manager is not None:
            try:
                db_manager.close()
                logger.info("Application shutdown complete")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()