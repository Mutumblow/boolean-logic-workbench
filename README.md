# Boolean Logic Workbench

A native Qt desktop application for Boolean logic with up to eight variables (A–H). It accepts canonical disjunctive or conjunctive forms, generates the equivalent form, editable truth tables, and a draggable gate scheme. Named outputs let you model multi-output circuits such as demultiplexers. A PDF export includes the forms, tables, and gate diagram.

The interface uses Qt Quick and PySide6, so the same QML application is touch-friendly and can also be packaged for Android. It is not a browser application.

## Run on desktop

Requires Python 3.10 or later and a supported PySide6 release.

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Entering forms

- Select **Disjunctive (SOP)** and enter products joined by `+`, for example `A'B'C'D'E' + ABCDE`. Terms may omit variables; omitted variables are expanded over both values. For example, `A'B` covers all rows where A=0 and B=1.
- Select **Conjunctive (POS)** and enter a product of sums containing every detected variable, or use the table notation `ΠP(1, 2, 3)`. In `ΠP(...)`, the indices identify the table cells where the function is 0.
- A prime after a variable means its negation. Whitespace is optional.
- The table keeps a four-variable base; the total is inferred from the highest variable letter used, from A through H. Index shorthand is accepted as `Σm(0, 3, 15)` for SOP and `ΠM(1, 2, 8)` for POS; for index-only expressions, the variable count is inferred from the largest index (with a four-variable minimum).
- `0` and `1` are accepted as constant functions.

Each table card retains the four-variable layout: columns are ordered `A'B'`, `A'B`, `AB`, `AB'`, and rows are ordered `C'D'`, `C'D`, `CD`, `CD'`. For variables after D, one separate 4-by-4 table is shown for every combination of fixed extra-variable values. All cards are in the Truth table tab, and P indices use the full binary assignment across all variables. For four variables, the P-cell indices are:

```text
        A'B'  A'B  AB   AB'
C'D'    P0    P4   P12  P8
C'D     P1    P5   P13  P9
CD      P3    P7   P15  P11
CD'     P2    P6   P14  P10
```

Each cell shows its value and minterm label, such as `1(P4)`; click a cell to toggle its value. Add and select named outputs in the function editor; every output has its own forms, editable table cards, and generated gate path. Table edits update that output's canonical forms and regenerate the multi-output scheme. Empty outputs start at 0, so use **Clear values** to reset the selected output.

The conjunctive form is displayed using the false-cell indices as `ΠP(...)`. The SOP gate scheme is generated from the true P cells regardless of whether the function was entered as SOP, POS, or through the table. Use **Edit SOP input** or **Edit POS input** to switch the editor to either canonical form.

When the input is an SOP expression, its product terms are used directly as AND gates, so omitted variables stay omitted from the gate inputs. For a POS or truth-table input, the equivalent SOP is minimized before the gate scheme is generated.

Formula-generated schemes use variable input rails, shared inverters, aligned product gates, a combining OR gate, and an output terminal. In the diagram, `A` is the input rail before the inverter; its branches marked with junction dots feed products that use positive `A`. The inverter output rail is labeled `A'` and feeds products that use negated `A`. The same applies to the other variables. On the scheme tab, use **Fit scheme**, the zoom slider, and the scrollbars to view large circuits. Drag individual gates to rearrange them. Press **Ctrl+Z** or choose **Undo** to reverse the latest gate move, added gate, connection, or MUX generation. Wires use distinct colors and spaced connection points. PDF export uses the current gate positions and same routes, scaling the complete layout uniformly to fit.

Enter and calculate any supported function in the Function tab, then choose **Synthesize f as 4:1 MUX** on the scheme tab. The app decomposes the selected truth table using `A` and `B` as select inputs; `I3`, `I2`, `I1`, and `I0` become the corresponding function of the remaining variables for selector values `00`, `01`, `10`, and `11`. The diagram builds those data-input functions from gates, then combines them as `f = A'B'I3 + A'BI2 + AB'I1 + ABI0`; it also includes the complementary `f'` output. This creates a MUX implementation of the active function without changing its canonical forms or truth tables.

## Custom gate schemes

On the **Gate scheme** tab, choose an AND, OR, NOT, INPUT, OUTPUT, 0, or 1 node and select **Add gate**. An optional label can name inputs and outputs. Select **Connect**, then tap/click a source node followed by a destination gate to draw a wire; inputs and constant nodes are sources, and output nodes are destinations. Drag any node to rearrange the scheme. The generated scheme can be supplemented with custom nodes and connections. Custom circuit wiring is a visual editor and does not replace the function entered in the canonical-form tab.

## Android

The QML interface is shared with the desktop app and supports touch dragging. To produce an Android package, use a Qt for Android / PySide6 Android deployment environment with the Android SDK, NDK, and Java toolchain installed. Android packaging is not performed by the desktop run command; follow the deployment instructions for the installed PySide6/Qt version and test the resulting package on a device or emulator.

## License and third-party software

This project's source code is released under the MIT license; see [LICENSE](./LICENSE). PySide6 and Qt are separate dependencies and are **not** covered by this project's MIT license. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for dependency licensing references and packaged-app cautions. Before publishing or distributing a packaged build, verify the terms for the exact dependencies and distribution.

## Tests

```powershell
python -m unittest discover -s tests -v
```
