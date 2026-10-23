import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from logic import BooleanLogic
from table_view import TruthTableView


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Boolean Logic Workbench")
    app.setOrganizationName("LogicBOOL")

    engine = QQmlApplicationEngine()
    logic = BooleanLogic()
    table_view = TruthTableView(logic)
    app.aboutToQuit.connect(table_view.cleanup)
    engine.rootContext().setContextProperty("logic", logic)
    engine.rootContext().setContextProperty("tableView", table_view)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("main.qml"))))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
