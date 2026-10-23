# Third-party notices

## PySide6 and Qt

This application depends on PySide6 (`PySide6>=6.8,<7`), which provides the
Qt for Python bindings and Qt runtime components. PySide6 and Qt are not
licensed under this project's MIT license. The PySide6 6.12.0 package metadata
declares `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; Qt for Python's
official documentation describes availability under LGPLv3/GPLv3 or a Qt
commercial license. The exact applicable terms depend on the version,
components, and distribution arrangement.

- Qt for Python licensing: <https://doc.qt.io/qtforpython-6/>
- Qt for Python third-party license information:
  <https://doc.qt.io/qtforpython-6/licenses.html>
- Qt's LGPL obligations overview:
  <https://www.qt.io/development/open-source-lgpl-obligations>

This repository contains application source code and a dependency declaration;
it does not intentionally bundle PySide6, Qt binaries, or Qt source code.
Installing or running the application may install those separate dependencies.
They remain subject to their own license terms.

Before distributing a packaged application, identify the exact Qt/PySide6
packages, Qt modules, plugins, and other components included. Review the terms
for that exact distribution, include any required license texts and notices,
and satisfy all applicable source-code, relinking, and installation-information
requirements. This notice is informational and is not a legal determination
that a particular distribution complies with those terms.

No other third-party source files or assets are intentionally included in this
repository at this time.
