# Boolean Logic Workbench

A native Qt desktop application for four-variable Boolean logic. It accepts a canonical disjunctive or conjunctive form and generates the equivalent form, a 4-by-4 truth table, and a draggable gate scheme. A PDF export includes the forms, truth table, and gate diagram.

The interface uses Qt Quick and PySide6, so the same QML application is touch-friendly and can also be packaged for Android. It is not a browser application.

## Run on desktop

Requires Python 3.10 or later and a supported PySide6 release.

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Entering forms

- Select **Disjunctive (SOP)** and enter products joined by `+`, for example `A'B'C'D' + A'B'CD`. Terms may omit variables; omitted variables are expanded over both values. For example, `A'B` covers all rows where A=0 and B=1.
- Select **Conjunctive (POS)** and enter a product of four-literal sums, or use the table notation `ΠP(1, 2, 3)`. In `ΠP(...)`, the indices identify the table cells where the function is 0.
- A prime after a variable means its negation. Whitespace is optional.
- Index shorthand is also accepted: `Σm(0, 3, 15)` for SOP and `ΠM(1, 2, 8)` for POS.
- `0` and `1` are accepted as constant functions.

The editable truth-table columns are ordered `A'B'`, `A'B`, `AB`, `AB'`, and its rows are ordered `C'D'`, `C'D`, `CD`, `CD'`. Its P-cell indices are:

```text
        A'B'  A'B  AB   AB'
C'D'    P0    P4   P12  P8
C'D     P1    P5   P13  P9
CD      P3    P7   P15  P11
CD'     P2    P6   P14  P10
```

Each cell shows its value and minterm label, such as `1(P4)`; click a cell to toggle its value. Table edits update both canonical forms and regenerate the gate scheme. Empty cells start at 0, so use **Clear values** to reset the whole table.

The conjunctive form is displayed using the false-cell indices as `ΠP(...)`. The SOP gate scheme is generated from the true P cells regardless of whether the function was entered as SOP, POS, or through the table. Use **Edit SOP input** or **Edit POS input** to switch the editor to either canonical form.

When the input is an SOP expression, its product terms are used directly as AND gates, so omitted variables stay omitted from the gate inputs. For a POS or truth-table input, the equivalent SOP is minimized before the gate scheme is generated.

On the scheme tab, use **Fit scheme**, the zoom slider, and the scrollbars to view large circuits. Drag individual gates to rearrange them. Wires use distinct colors and spaced connection points; routes that would cross unrelated gates wrap around them in separate lanes below the circuit. PDF export uses the current gate positions and same routes, scaling the complete layout uniformly to fit.

## Custom gate schemes

On the **Gate scheme** tab, choose an AND, OR, NOT, INPUT, OUTPUT, 0, or 1 node and select **Add gate**. An optional label can name inputs and outputs. Select **Connect**, then tap/click a source node followed by a destination gate to draw a wire; inputs and constant nodes are sources, and output nodes are destinations. Drag any node to rearrange the scheme. The generated scheme can be supplemented with custom nodes and connections. Custom circuit wiring is a visual editor and does not replace the function entered in the canonical-form tab.

## Android

The QML interface is shared with the desktop app and supports touch dragging. To produce an Android package, use a Qt for Android / PySide6 Android deployment environment with the Android SDK, NDK, and Java toolchain installed. Android packaging is not performed by the desktop run command; follow the deployment instructions for the installed PySide6/Qt version and test the resulting package on a device or emulator.

## License and third-party software

This project's source code is released under the MIT license; see [LICENSE](./LICENSE). PySide6 and Qt are separate dependencies and are **not** covered by this project's MIT license. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for dependency licensing references and packaged-app cautions. Before publishing or distributing a packaged build, follow the [public release checklist](./PUBLISHING.md) and verify the terms for the exact dependencies and distribution.

## Tests

```powershell
python -m unittest discover -s tests -v
```
