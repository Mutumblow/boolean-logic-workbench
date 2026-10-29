import re
from functools import lru_cache
from math import ceil
from typing import Any

from PySide6.QtCore import QMarginsF, QObject, Property, QUrl, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor, QFont, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen,
)
from PySide6.QtCore import QSizeF


VARIABLES = "ABCDEFGH"
TABLE_VARIABLES = "ABCD"
GRAY_ORDER = (0, 1, 3, 2)
Cube = tuple[int | None, ...]
WIRE_COLORS = (
    "#0072b2", "#d55e00", "#009e73", "#cc79a7",
    "#e69f00", "#56b4e9", "#882255", "#332288",
    "#117733", "#aa4499", "#44aa99", "#999933",
)


def _wire_color(source_id: str) -> str:
    if source_id.startswith("var_") and source_id[4:] in VARIABLES:
        color_index = VARIABLES.index(source_id[4:])
    elif source_id.startswith("not_") and source_id[4:] in VARIABLES:
        color_index = len(VARIABLES) + VARIABLES.index(source_id[4:])
    elif source_id.startswith("and_term_"):
        color_index = len(VARIABLES) * 2 + int(source_id.rsplit("_", 1)[1])
    elif source_id.startswith("custom_") and source_id[7:].isdigit():
        color_index = len(VARIABLES) * 2 + int(source_id[7:])
    else:
        color_index = sum(map(ord, source_id))
    if color_index < len(WIRE_COLORS):
        return WIRE_COLORS[color_index]
    return QColor.fromHsv((color_index * 137) % 360, 190, 190).name()


def _wire_route_points(
    wire: dict[str, Any], source: dict[str, Any], target: dict[str, Any]
) -> list[tuple[float, float]]:
    x1 = source["x"] + source["width"]
    y1 = source["y"] + wire["sourceOffset"]
    x2 = target["x"]
    y2 = target["y"] + wire["targetOffset"]
    direction = 1 if x2 >= x1 else -1
    launch_x = x1 + direction * (12 + wire["sourceRouteIndex"] * 6)
    approach_x = x2 - direction * (12 + wire["targetRouteIndex"] * 6)
    if wire.get("wrapSide"):
        return [
            (x1, y1),
            (launch_x, y1),
            (launch_x, wire["wrapLaneY"]),
            (approach_x, wire["wrapLaneY"]),
            (approach_x, y2),
            (x2, y2),
        ]
    channel_x = launch_x + (
        approach_x - launch_x
    ) * wire["routeChannelFraction"]
    lane_y = (y1 + y2) / 2 + wire["routeLaneOffset"]
    return [
        (x1, y1),
        (launch_x, y1),
        (channel_x, y1),
        (channel_x, lane_y),
        (approach_x, lane_y),
        (approach_x, y2),
        (x2, y2),
    ]


def _path_intersects_node(
    points: list[tuple[float, float]], node: dict[str, Any], clearance: float = 8
) -> bool:
    left = node["x"] - clearance
    right = node["x"] + node["width"] + clearance
    top = node["y"] - clearance
    bottom = node["y"] + node["height"] + clearance
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 == x2 and left < x1 < right:
            if max(min(y1, y2), top) < min(max(y1, y2), bottom):
                return True
        elif y1 == y2 and top < y1 < bottom:
            if max(min(x1, x2), left) < min(max(x1, x2), right):
                return True
    return False


def _index_from_literals(
    tokens: list[tuple[str, bool]], *, product: bool, variables: str = "ABCD"
) -> int:
    names = [name for name, _ in tokens]
    if sorted(names) != sorted(variables):
        expected = ", ".join(variables)
        raise ValueError(f"Each canonical term must contain {expected} exactly once.")

    bits: dict[str, int] = {}
    for name, negated in tokens:
        bits[name] = int(not negated) if product else int(negated)
    return sum(bits[name] << (len(variables) - 1 - offset)
               for offset, name in enumerate(variables))


def _parse_literals(
    text: str, *, product: bool, allowed_variables: str = VARIABLES
) -> list[tuple[str, bool]]:
    if product:
        pattern = rf"([{allowed_variables}])\s*('?)"
        parts = re.findall(pattern, text)
        if re.sub(r"\s+", "", "".join(name + prime for name, prime in parts)) != re.sub(
            r"\s+", "", text
        ):
            raise ValueError(f"Invalid literal in canonical term: {text!r}.")
        return [(name, bool(prime)) for name, prime in parts]

    parts = re.split(r"\s*\+\s*", text.strip())
    tokens: list[tuple[str, bool]] = []
    for part in parts:
        match = re.fullmatch(rf"\s*([{allowed_variables}])\s*('?)\s*", part)
        if match is None:
            raise ValueError(f"Invalid literal in canonical term: {part!r}.")
        tokens.append((match.group(1), bool(match.group(2))))
    return tokens


def infer_variable_count(text: str) -> int:
    variables = re.findall(r"[A-H]", text)
    if variables:
        return max(4, max(VARIABLES.index(variable) + 1 for variable in variables))
    shorthand = re.search(r"\(([^)]*)\)", text)
    if shorthand and shorthand.group(1).strip():
        try:
            indices = [int(value.strip()) for value in shorthand.group(1).split(",")]
        except ValueError:
            return 4
        if indices and all(index >= 0 for index in indices):
            return max(4, max(indices).bit_length())
    return 4


def parse_sop_cubes(text: str, variables: str = "ABCD") -> list[Cube]:
    source = text.strip()
    if source in {"0", "1"}:
        return [] if source == "0" else [(None,) * len(variables)]

    shorthand = re.fullmatch(r"(?:Σ|Sigma)\s*m\s*\(([^)]*)\)", source, re.IGNORECASE)
    if shorthand:
        values = shorthand.group(1).strip()
        if not values:
            return []
        try:
            indices = [int(value.strip()) for value in values.split(",")]
        except ValueError as error:
            raise ValueError("Minterm indices must be non-negative integers.") from error
        maximum_index = (1 << len(variables)) - 1
        if any(index < 0 or index > maximum_index for index in indices):
            raise ValueError(f"Minterm indices must be from 0 to {maximum_index}.")
        return [
            tuple((index >> (len(variables) - 1 - offset)) & 1
                  for offset in range(len(variables)))
            for index in sorted(set(indices))
        ]

    terms = re.split(r"\s*\+\s*", source)
    if not terms or any(not term.strip() for term in terms):
        example = "".join(variables)
        raise ValueError(f"Enter a sum of canonical products, such as {example}.")
    cubes = []
    for term in terms:
        clean = term.strip()
        if clean.startswith("(") and clean.endswith(")"):
            clean = clean[1:-1]
        literals = _parse_literals(clean, product=True)
        names = [name for name, _ in literals]
        if len(names) != len(set(names)):
            raise ValueError("Each variable may appear only once in a product term.")
        assigned_bits = {name: int(not negated) for name, negated in literals}
        if any(name not in variables for name in names):
            raise ValueError("The expression uses a variable outside the detected range.")
        cubes.append(tuple(assigned_bits.get(name) for name in variables))
    return cubes


def expand_cubes(cubes: list[Cube]) -> set[int]:
    minterms: set[int] = set()
    for cube in cubes:
        free_positions = [offset for offset, bit in enumerate(cube) if bit is None]
        for combination in range(1 << len(free_positions)):
            bits = list(cube)
            for free_offset, position in enumerate(free_positions):
                bits[position] = (
                    combination >> (len(free_positions) - free_offset - 1)
                ) & 1
            minterms.add(sum(
                int(bit) << (len(bits) - 1 - offset)
                for offset, bit in enumerate(bits)
            ))
    return minterms


def parse_sop(text: str, variables: str = "ABCD") -> set[int]:
    return expand_cubes(parse_sop_cubes(text, variables))


def minimize_sop(minterms: set[int], variable_count: int = 4) -> list[Cube]:
    if not minterms:
        return []
    if len(minterms) == 1 << variable_count:
        return [(None,) * variable_count]

    current = {tuple((index >> (variable_count - 1 - offset)) & 1
                     for offset in range(variable_count))
               for index in minterms}
    primes: set[Cube] = set()
    while current:
        combined: set[Cube] = set()
        used: set[Cube] = set()
        groups: dict[tuple[tuple[int, ...], int], list[Cube]] = {}
        for cube in current:
            dash_pattern = tuple(offset for offset, bit in enumerate(cube) if bit is None)
            ones_count = sum(bit == 1 for bit in cube)
            groups.setdefault((dash_pattern, ones_count), []).append(cube)
        for dash_pattern, ones_count in groups:
            left_cubes = groups[(dash_pattern, ones_count)]
            right_cubes = groups.get((dash_pattern, ones_count + 1), [])
            for left in left_cubes:
                for right in right_cubes:
                    differences = [offset for offset, (a, b) in enumerate(zip(left, right))
                                   if a != b]
                    if len(differences) != 1:
                        continue
                    offset = differences[0]
                    if left[offset] is None or right[offset] is None:
                        continue
                    merged = list(left)
                    merged[offset] = None
                    combined.add(tuple(merged))
                    used.add(left)
                    used.add(right)
        primes.update(current - used)
        current = combined

    prime_list = sorted(primes, key=lambda cube: tuple(-1 if bit is None else bit for bit in cube))
    covers = []
    for cube in prime_list:
        covered = {
            index for index in minterms
            if all(bit is None or bit == ((index >> (variable_count - 1 - offset)) & 1)
                   for offset, bit in enumerate(cube))
        }
        covers.append(covered)

    target_mask = sum(1 << index for index in minterms)
    cover_masks = [
        sum(1 << index for index in covered) for covered in covers
    ]
    literals = [
        sum(bit is not None for bit in cube) for cube in prime_list
    ]
    selected: set[int] = set()
    uncovered_mask = target_mask
    while True:
        essential: set[int] = set()
        remaining_bits = uncovered_mask
        while remaining_bits:
            bit = remaining_bits & -remaining_bits
            candidates = [
                index for index, cover_mask in enumerate(cover_masks)
                if index not in selected and cover_mask & bit
            ]
            if len(candidates) == 1:
                essential.add(candidates[0])
            remaining_bits ^= bit
        if not essential:
            break
        selected.update(essential)
        for index in essential:
            uncovered_mask &= ~cover_masks[index]

    candidates = [
        index for index, mask in enumerate(cover_masks)
        if index not in selected and mask & uncovered_mask
    ]
    clipped_masks = {
        index: cover_masks[index] & uncovered_mask for index in candidates
    }
    dominated: set[int] = set()
    for candidate in candidates:
        for other in candidates:
            if candidate == other:
                continue
            candidate_cover = clipped_masks[candidate]
            other_cover = clipped_masks[other]
            if candidate_cover & other_cover != candidate_cover:
                continue
            if literals[other] < literals[candidate] or (
                literals[other] == literals[candidate]
                and other < candidate
            ):
                dominated.add(candidate)
                break
    candidates = [index for index in candidates if index not in dominated]

    covering_by_minterm: dict[int, tuple[int, ...]] = {}
    remaining_bits = uncovered_mask
    while remaining_bits:
        bit = remaining_bits & -remaining_bits
        covering_by_minterm[bit] = tuple(
            index for index in candidates if clipped_masks[index] & bit
        )
        remaining_bits ^= bit

    @lru_cache(maxsize=None)
    def cover(remaining: int) -> tuple[int, int, tuple[int, ...]] | None:
        if not remaining:
            return 0, 0, ()
        bits = []
        remaining_bits = remaining
        while remaining_bits:
            bit = remaining_bits & -remaining_bits
            bits.append(bit)
            remaining_bits ^= bit
        selected_bit = min(
            bits,
            key=lambda bit: sum(
                bool(clipped_masks[index] & remaining)
                for index in covering_by_minterm[bit]
            ),
        )
        best: tuple[int, int, tuple[int, ...]] | None = None
        for index in covering_by_minterm[selected_bit]:
            next_remaining = remaining & ~clipped_masks[index]
            if next_remaining == remaining:
                continue
            subresult = cover(next_remaining)
            if subresult is None:
                continue
            selection = tuple(sorted((*subresult[2], index)))
            result = (
                subresult[0] + 1,
                subresult[1] + literals[index],
                selection,
            )
            if best is None or result < best:
                best = result
        return best

    solution = cover(uncovered_mask)
    if solution is None:
        raise ValueError("The minterms could not be covered by the available implicants.")
    selected.update(solution[2])
    return [prime_list[index] for index in sorted(selected)]


def parse_pos(text: str, variables: str = "ABCD") -> set[int]:
    source = text.strip()
    if source in {"0", "1"}:
        return set(range(1 << len(variables))) if source == "0" else set()

    shorthand = re.fullmatch(r"(?:Π|Pi)\s*(?:M|P)\s*\(([^)]*)\)", source, re.IGNORECASE)
    if shorthand:
        values = shorthand.group(1).strip()
        if not values:
            return set()
        try:
            indices = [int(value.strip()) for value in values.split(",")]
        except ValueError as error:
            raise ValueError("Maxterm indices must be non-negative integers.") from error
        maximum_index = (1 << len(variables)) - 1
        if any(index < 0 or index > maximum_index for index in indices):
            raise ValueError(f"Maxterm indices must be from 0 to {maximum_index}.")
        return set(indices)

    clauses = re.findall(r"\(([^()]*)\)", source)
    remainder = re.sub(r"\([^()]*\)", "", source)
    if not clauses or remainder.strip(" \t\r\n·*."):
        raise ValueError("Enter a product of canonical sums, such as (A+B+C+D)(A+B+C+D').")

    zero_indices: set[int] = set()
    for clause in clauses:
        zero_indices.add(_index_from_literals(
            _parse_literals(clause, product=False),
            product=False,
            variables=variables,
        ))
    return zero_indices


def _literal(name: str, bit: int) -> str:
    return name if bit else f"{name}'"


def format_sop(minterms: set[int], variables: str = "ABCD") -> str:
    if not minterms:
        return "0"
    if len(minterms) == 1 << len(variables):
        return "1"
    terms = []
    for index in sorted(minterms):
        terms.append("".join(
            _literal(name, (index >> (len(variables) - 1 - offset)) & 1)
            for offset, name in enumerate(variables)
        ))
    return " + ".join(terms)


def format_pos(zero_indices: set[int], variable_count: int = 4) -> str:
    if not zero_indices:
        return "1"
    if len(zero_indices) == 1 << variable_count:
        return "0"
    indices = ", ".join(str(index) for index in sorted(zero_indices))
    return f"ΠP({indices})"


def truth_table_panels(
    minterms: set[int], variable_count: int = 4
) -> list[dict[str, Any]]:
    extra_count = variable_count - len(TABLE_VARIABLES)
    panels = []
    for extra_index in range(1 << extra_count):
        extra_bits = tuple(
            (extra_index >> (extra_count - offset - 1)) & 1
            for offset in range(extra_count)
        )
        suffix = sum(
            bit << (extra_count - offset - 1)
            for offset, bit in enumerate(extra_bits)
        )
        rows = []
        for cd in GRAY_ORDER:
            row_values = []
            cells = []
            for ab in GRAY_ORDER:
                index = (((ab << 2) | cd) << extra_count) | suffix
                value = int(index in minterms)
                row_values.append(value)
                cells.append({"index": index, "value": value})
            rows.append({
                "label": "".join(
                    _literal(name, (cd >> (1 - offset)) & 1)
                    for offset, name in enumerate("CD")
                ),
                "values": row_values,
                "cells": cells,
            })
        assignment = ", ".join(
            f"{VARIABLES[len(TABLE_VARIABLES) + offset]}={bit}"
            for offset, bit in enumerate(extra_bits)
        )
        panels.append({
            "sliceIndex": extra_index,
            "assignment": assignment,
            "rows": rows,
        })
    return panels


def truth_table(minterms: set[int], variable_count: int = 4) -> list[dict[str, Any]]:
    return truth_table_panels(minterms, variable_count)[0]["rows"]


class BooleanLogic(QObject):
    changed = Signal()
    schemeChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._minterms: set[int] = set()
        self._has_result = False
        self._error = ""
        self._sop = ""
        self._pos = ""
        self._rows = truth_table(set())
        self._variable_count = 4
        self._outputs: list[dict[str, Any]] = [{
            "id": "F",
            "name": "F",
            "hasResult": False,
            "source": "",
            "mode": "SOP",
            "minterms": set(),
            "cubes": [],
            "sop": "",
            "pos": "",
        }]
        self._next_output_id = 1
        self._active_output_id = "F"
        self._table_panels: list[dict[str, Any]] = []
        self._nodes: list[dict[str, Any]] = []
        self._connections: list[dict[str, Any]] = []
        self._scheme_width = 1000
        self._scheme_height = 620
        self._scheme_description = ""
        self._node_positions: dict[str, tuple[float, float]] = {}
        self._scheme_cubes: list[Cube] = []
        self._refresh_derived_state()

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Property(bool, notify=changed)
    def hasResult(self) -> bool:
        return self._has_result

    @Property(bool, notify=changed)
    def hasAnyResult(self) -> bool:
        return any(output["hasResult"] for output in self._outputs)

    @Property(str, notify=changed)
    def sop(self) -> str:
        return self._sop

    @Property(str, notify=changed)
    def pos(self) -> str:
        return self._pos

    @Property(int, notify=changed)
    def variableCount(self) -> int:
        return self._variable_count

    @Property(str, notify=changed)
    def activeOutputId(self) -> str:
        return self._active_output_id

    @Property(str, notify=changed)
    def activeOutputName(self) -> str:
        return self._active_output()["name"]

    @Property(str, notify=changed)
    def activeSource(self) -> str:
        return self._active_output()["source"]

    @Property(str, notify=changed)
    def activeMode(self) -> str:
        return self._active_output()["mode"]

    @Property("QVariantList", notify=changed)
    def outputOptions(self) -> list[dict[str, str]]:
        return [{"id": output["id"], "name": output["name"]}
                for output in self._outputs]

    @Property("QVariantList", notify=changed)
    def tableRows(self) -> list[dict[str, Any]]:
        return self._rows

    @Property("QVariantList", notify=changed)
    def tablePanels(self) -> list[dict[str, Any]]:
        return self._table_panels

    @Property("QVariantList", notify=schemeChanged)
    def schemeNodes(self) -> list[dict[str, Any]]:
        return self._nodes

    @Property("QVariantList", notify=schemeChanged)
    def connections(self) -> list[dict[str, Any]]:
        return self._connections

    @Property(int, notify=schemeChanged)
    def schemeWidth(self) -> int:
        return self._scheme_width

    @Property(int, notify=schemeChanged)
    def schemeHeight(self) -> int:
        return self._scheme_height

    @Property(bool, notify=schemeChanged)
    def hasScheme(self) -> bool:
        return bool(self._nodes)

    @Property(str, notify=schemeChanged)
    def schemeDescription(self) -> str:
        return self._scheme_description

    @Slot(str, str)
    def calculate(self, mode: str, text: str) -> None:
        if mode not in {"SOP", "POS"}:
            self._set_error("Choose either canonical SOP or canonical POS input.")
            return
        output = self._active_output()
        proposed_source = text.strip()
        if not proposed_source:
            self._set_error("Enter a canonical form before generating results.")
            return
        sources = [
            proposed_source if item["id"] == self._active_output_id else item["source"]
            for item in self._outputs
        ]
        variable_count = max(
            (infer_variable_count(source) for source in sources if source),
            default=4,
        )
        if variable_count > len(VARIABLES):
            self._set_error(
                f"The workbench supports up to {len(VARIABLES)} variables (A–H)."
            )
            return
        try:
            values = [
                self._evaluate_function(
                    mode if item["id"] == self._active_output_id else item["mode"],
                    proposed_source if item["id"] == self._active_output_id else item["source"],
                    variable_count,
                )
                if (proposed_source if item["id"] == self._active_output_id else item["source"])
                else (set(), [])
                for item in self._outputs
            ]
        except ValueError as error:
            self._set_error(str(error))
            return

        output["source"] = proposed_source
        output["mode"] = mode
        output["hasResult"] = True
        self._variable_count = variable_count
        for item, (minterms, cubes) in zip(self._outputs, values):
            item["minterms"] = minterms
            item["cubes"] = cubes
            item["hasResult"] = item["hasResult"] or bool(
                item["id"] == self._active_output_id
            )
        self._refresh_derived_state()

    def _active_output(self) -> dict[str, Any]:
        return next(
            output for output in self._outputs
            if output["id"] == self._active_output_id
        )

    def _evaluate_function(
        self, mode: str, text: str, variable_count: int
    ) -> tuple[set[int], list[Cube]]:
        source_variable_count = infer_variable_count(text)
        if source_variable_count > variable_count:
            raise ValueError("An output uses more variables than the current workspace.")
        variables = VARIABLES[:source_variable_count]
        if mode == "SOP":
            cubes = parse_sop_cubes(text, variables)
            minterms = expand_cubes(cubes)
        elif mode == "POS":
            minterms = set(range(1 << source_variable_count)) - parse_pos(
                text, variables
            )
            cubes = minimize_sop(minterms, source_variable_count)
        else:
            raise ValueError("Choose either canonical SOP or canonical POS input.")

        extra_count = variable_count - source_variable_count
        if extra_count:
            minterms = {
                (minterm << extra_count) | suffix
                for minterm in minterms
                for suffix in range(1 << extra_count)
            }
            cubes = [cube + (None,) * extra_count for cube in cubes]
        return minterms, cubes

    @Slot(str)
    def selectOutput(self, output_id: str) -> None:
        if output_id not in {output["id"] for output in self._outputs}:
            self._set_error("Choose an existing output.")
            return
        self._active_output_id = output_id
        self._sync_active_output()
        self._error = ""
        self.changed.emit()

    @Slot(str)
    def addOutput(self, name: str) -> None:
        output_name = name.strip()
        if not output_name:
            suffix = 1
            existing = {output["name"] for output in self._outputs}
            while f"Y{suffix}" in existing:
                suffix += 1
            output_name = f"Y{suffix}"
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}", output_name):
            self._set_error("Output names must start with a letter and use up to 16 letters, numbers, or underscores.")
            return
        if any(output["name"] == output_name for output in self._outputs):
            self._set_error("Output names must be unique.")
            return
        output_id = f"output_{self._next_output_id}"
        self._next_output_id += 1
        self._outputs.append({
            "id": output_id,
            "name": output_name,
            "hasResult": False,
            "source": "",
            "mode": "SOP",
            "minterms": set(),
            "cubes": [],
            "sop": "",
            "pos": "",
        })
        self._active_output_id = output_id
        self._refresh_derived_state()

    @Slot()
    def removeActiveOutput(self) -> None:
        if len(self._outputs) == 1:
            self._set_error("At least one output must remain.")
            return
        self._outputs = [
            output for output in self._outputs
            if output["id"] != self._active_output_id
        ]
        self._active_output_id = self._outputs[0]["id"]
        self._variable_count = max(
            (
                infer_variable_count(output["source"])
                for output in self._outputs if output["source"]
            ),
            default=4,
        )
        try:
            for output in self._outputs:
                if output["source"]:
                    minterms, cubes = self._evaluate_function(
                        output["mode"], output["source"], self._variable_count
                    )
                    output["minterms"] = minterms
                    output["cubes"] = cubes
        except ValueError as error:
            self._set_error(str(error))
            return
        self._refresh_derived_state()

    @Slot(int, int)
    def setTableCell(self, index: int, value: int) -> None:
        self.setOutputTableCell(self._active_output_id, index, value)

    @Slot(str, int, int)
    def setOutputTableCell(self, output_id: str, index: int, value: int) -> None:
        output = next(
            (item for item in self._outputs if item["id"] == output_id), None
        )
        if output is None:
            self._set_error("Choose an existing output before editing the table.")
            return
        if not 0 <= index < 1 << self._variable_count:
            self._set_error(
                f"Truth-table P indices must be from 0 to {(1 << self._variable_count) - 1}."
            )
            return
        if value not in (0, 1):
            self._set_error("Truth-table cell values must be 0 or 1.")
            return
        minterms = set(output["minterms"])
        if value:
            minterms.add(index)
        else:
            minterms.discard(index)
        output["hasResult"] = True
        output["source"] = format_sop(minterms, VARIABLES[:self._variable_count])
        output["mode"] = "SOP"
        output["minterms"] = minterms
        output["cubes"] = minimize_sop(minterms, self._variable_count)
        self._refresh_derived_state()

    @Slot()
    def clearTable(self) -> None:
        output = self._active_output()
        output["minterms"] = set()
        output["source"] = "0"
        output["mode"] = "SOP"
        output["cubes"] = []
        output["hasResult"] = True
        self._refresh_derived_state()

    def _refresh_derived_state(self) -> None:
        variables = VARIABLES[:self._variable_count]
        for output in self._outputs:
            minterms = output["minterms"]
            output["sop"] = format_sop(minterms, variables)
            output["pos"] = format_pos(
                set(range(1 << self._variable_count)) - minterms,
                self._variable_count,
            )
        active = self._active_output()
        self._minterms = set(active["minterms"])
        self._has_result = bool(active["hasResult"])
        self._sop = active["sop"]
        self._pos = active["pos"]
        self._scheme_cubes = active["cubes"]
        self._rows = truth_table(self._minterms, self._variable_count)
        self._table_panels = [
            {
                "outputId": output["id"],
                "outputName": output["name"],
                "hasResult": output["hasResult"],
                "sliceIndex": panel["sliceIndex"],
                "assignment": panel["assignment"],
                "rows": panel["rows"],
            }
            for output in self._outputs
            for panel in truth_table_panels(
                output["minterms"] if output["hasResult"] else set(),
                self._variable_count,
            )
        ]
        self._error = ""
        self._build_scheme()
        self._assign_wire_routes()
        self.changed.emit()
        self.schemeChanged.emit()

    def _sync_active_output(self) -> None:
        active = self._active_output()
        self._minterms = set(active["minterms"])
        self._has_result = bool(active["hasResult"])
        self._sop = active["sop"]
        self._pos = active["pos"]
        self._scheme_cubes = active["cubes"]
        self._rows = truth_table(self._minterms, self._variable_count)

    def _apply_function(
        self, minterms: set[int], cubes: list[Cube] | None = None
    ) -> None:
        output = self._active_output()
        output["minterms"] = minterms
        output["cubes"] = (
            cubes if cubes is not None
            else minimize_sop(minterms, self._variable_count)
        )
        output["source"] = format_sop(
            minterms, VARIABLES[:self._variable_count]
        )
        output["mode"] = "SOP"
        output["hasResult"] = True
        self._refresh_derived_state()

    @Slot(str, float, float)
    def moveNode(self, node_id: str, x: float, y: float) -> None:
        if node_id not in self._node_positions:
            return
        node = next((item for item in self._nodes if item["id"] == node_id), None)
        if node is None:
            return
        x = max(0, min(float(x), self._scheme_width - node["width"]))
        y = max(0, min(float(y), self._scheme_height - node["height"]))
        self._node_positions[node_id] = (x, y)
        node["x"] = x
        node["y"] = y
        self._assign_wire_routes()
        self.schemeChanged.emit()

    @Slot(str, str)
    def addGate(self, gate_type: str, label: str) -> None:
        kind = gate_type.upper()
        valid_types = {"AND", "OR", "NOT", "INPUT", "OUTPUT", "0", "1"}
        if kind not in valid_types:
            self._set_error(f"Unsupported gate type: {gate_type}.")
            return
        custom_label = label.strip()
        if len(custom_label) > 24:
            self._set_error("Gate labels must be 24 characters or fewer.")
            return

        count = sum(node["type"] == kind for node in self._nodes)
        if custom_label:
            node_label = custom_label
        elif kind == "INPUT":
            node_label = f"X{count + 1}"
        elif kind == "OUTPUT":
            node_label = "F"
        else:
            node_label = f"{kind}{count + 1}" if kind not in {"0", "1"} else kind

        node_id = f"custom_{len(self._nodes) + 1}"
        x = 40 + (len(self._nodes) % 5) * 170
        y = 40 + (len(self._nodes) // 5) * 140
        node_kind = "CONSTANT" if kind in {"0", "1"} else kind
        node = {
            "id": node_id, "label": node_label, "type": node_kind,
            "x": float(x), "y": float(y), "width": 110, "height": 100,
        }
        self._nodes.append(node)
        self._node_positions[node_id] = (float(x), float(y))
        self._scheme_width = max(self._scheme_width, x + 150)
        self._scheme_height = max(self._scheme_height, y + 130)
        self._assign_wire_routes()
        self._error = ""
        self.changed.emit()
        self.schemeChanged.emit()

    @Slot(str, str)
    def connectNodes(self, source_id: str, target_id: str) -> None:
        source = next((node for node in self._nodes if node["id"] == source_id), None)
        target = next((node for node in self._nodes if node["id"] == target_id), None)
        if source is None or target is None:
            self._set_error("Select two existing nodes to connect.")
            return
        if source_id == target_id:
            self._set_error("A gate cannot connect to itself.")
            return
        if source["type"] == "OUTPUT":
            self._set_error("An output node cannot be used as a signal source.")
            return
        if target["type"] in {"INPUT", "CONSTANT"}:
            self._set_error("Input and constant nodes cannot receive connections.")
            return
        if any(wire["source"] == source_id and wire["target"] == target_id
               for wire in self._connections):
            self._set_error("These nodes are already connected.")
            return

        incoming = [wire for wire in self._connections if wire["target"] == target_id]
        max_inputs = target.get("maxInputs", 1 if target["type"] in {"NOT", "OUTPUT"} else 4)
        if len(incoming) >= max_inputs:
            self._set_error(f"{target['label']} already has all its inputs connected.")
            return

        adjacency: dict[str, list[str]] = {}
        for wire in self._connections:
            adjacency.setdefault(wire["source"], []).append(wire["target"])
        stack = [target_id]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current == source_id:
                self._set_error("That connection would create a logic loop.")
                return
            if current not in visited:
                visited.add(current)
                stack.extend(adjacency.get(current, []))

        self._connections.append({
            "source": source_id,
            "target": target_id,
            "sourceOffset": source["height"] / 2,
            "targetOffset": 15 + (len(incoming) + 1) * 70 / (max_inputs + 1),
            "color": _wire_color(source_id),
        })
        self._assign_wire_routes()
        self._error = ""
        self.changed.emit()
        self.schemeChanged.emit()

    @Slot()
    def generateMultiplexer(self) -> None:
        output = self._active_output()
        if not output["hasResult"]:
            self._set_error("Enter or calculate f before generating its MUX scheme.")
            return

        self._nodes = []
        self._connections = []
        self._node_positions = {}
        self._scheme_width = 1800
        self._scheme_height = 800
        self._scheme_description = (
            "4:1 MUX decomposition of the selected f; A and B are select inputs, "
            "and I0-I3 are derived functions of the remaining variables."
        )

        def add_node(
            node_id: str, label: str, kind: str, x: float, y: float,
            max_inputs: int = 4,
        ) -> None:
            node = {
                "id": node_id,
                "label": label,
                "type": kind,
                "x": x,
                "y": y,
                "width": 110,
                "height": 100,
                "maxInputs": max_inputs,
            }
            self._nodes.append(node)
            self._node_positions[node_id] = (x, y)

        def connect(source: str, target: str) -> None:
            self._connections.append({
                "source": source,
                "target": target,
                "sourceOffset": 50,
                "targetOffset": 50,
                "color": _wire_color(source),
            })

        variable_count = self._variable_count
        remaining_variables = VARIABLES[2:variable_count]
        selector_inputs = ((0, 0, "I3"), (0, 1, "I2"),
                           (1, 0, "I1"), (1, 1, "I0"))
        data_functions: list[tuple[str, set[int], list[Cube]]] = []
        for selector_a, selector_b, input_name in selector_inputs:
            data_minterms = {
                minterm & ((1 << (variable_count - 2)) - 1)
                for minterm in output["minterms"]
                if (minterm >> (variable_count - 1)) & 1 == selector_a
                and (minterm >> (variable_count - 2)) & 1 == selector_b
            }
            data_cubes = minimize_sop(data_minterms, variable_count - 2)
            data_functions.append((input_name, data_minterms, data_cubes))

        input_y: dict[str, float] = {}
        for index, variable in enumerate(VARIABLES[:variable_count]):
            y = 45 + index * 135
            input_y[variable] = y
            add_node(f"mux_var_{variable}", variable, "INPUT", 20, y, 0)

        negated_variables = {
            variable
            for _, _, cubes in data_functions
            for cube in cubes
            for offset, variable in enumerate(remaining_variables)
            if cube[offset] == 0
        } | {"A", "B"}
        for variable in VARIABLES[:variable_count]:
            if variable in negated_variables:
                add_node(
                    f"mux_not_{variable}", f"{variable}'", "NOT",
                    200, input_y[variable], 1,
                )
                connect(f"mux_var_{variable}", f"mux_not_{variable}")

        data_signal_ids: dict[str, str] = {}
        data_centers: dict[str, float] = {}
        cursor_y = 45.0
        for input_name, data_minterms, cubes in data_functions:
            function_text = format_sop(data_minterms, remaining_variables)
            if not cubes or all(bit is None for bit in cubes[0]):
                value = int(bool(data_minterms))
                node_id = f"mux_data_{input_name}"
                center_y = cursor_y + 50
                add_node(
                    node_id, str(value), "CONSTANT", 720, center_y - 50, 0
                )
                data_signal_ids[input_name] = node_id
                data_centers[input_name] = center_y
                cursor_y += 150
                continue

            term_ids: list[str] = []
            term_centers: list[float] = []
            for cube_index, cube in enumerate(cubes):
                term_id = f"mux_data_{input_name}_term_{cube_index}"
                term_y = cursor_y + cube_index * 130
                literals = [
                    (variable, bit)
                    for variable, bit in zip(remaining_variables, cube)
                    if bit is not None
                ]
                label = (
                    f"{input_name}: {function_text}"
                    if len(cubes) == 1
                    else f"{input_name} term {cube_index + 1}"
                )
                add_node(term_id, label, "AND", 470, term_y, max(1, len(literals)))
                for variable, bit in literals:
                    source = (
                        f"mux_var_{variable}" if bit
                        else f"mux_not_{variable}"
                    )
                    connect(source, term_id)
                term_ids.append(term_id)
                term_centers.append(term_y + 50)

            if len(term_ids) == 1:
                signal_id = term_ids[0]
            else:
                signal_id = f"mux_data_{input_name}_or"
                center_y = sum(term_centers) / len(term_centers)
                add_node(signal_id, f"{input_name}: {function_text}", "OR",
                         720, center_y - 50, len(term_ids))
                for term_id in term_ids:
                    connect(term_id, signal_id)
            data_signal_ids[input_name] = signal_id
            data_centers[input_name] = sum(term_centers) / len(term_centers)
            cursor_y += len(term_ids) * 130 + 40

        selector_source = {
            (0, 0): ("mux_not_A", "mux_not_B"),
            (0, 1): ("mux_not_A", "mux_var_B"),
            (1, 0): ("mux_var_A", "mux_not_B"),
            (1, 1): ("mux_var_A", "mux_var_B"),
        }
        mux_term_ids = []
        mux_term_centers = []
        for selector_a, selector_b, input_name in selector_inputs:
            center_y = data_centers[input_name]
            term_id = f"mux_select_term_{input_name}"
            add_node(term_id, f"AND {input_name}", "AND", 1010,
                     center_y - 50, 3)
            connect(data_signal_ids[input_name], term_id)
            for source in selector_source[(selector_a, selector_b)]:
                connect(source, term_id)
            mux_term_ids.append(term_id)
            mux_term_centers.append(center_y)

        output_center_y = sum(mux_term_centers) / len(mux_term_centers)
        add_node("mux_or", "OR", "OR", 1260, output_center_y - 50, 4)
        for term_id in mux_term_ids:
            connect(term_id, "mux_or")

        add_node("mux_output_F", "f", "OUTPUT", 1510,
                 output_center_y - 65, 1)
        add_node("mux_not_F", "NOT f", "NOT", 1510,
                 output_center_y + 65, 1)
        add_node("mux_output_Fbar", "f'", "OUTPUT", 1690,
                 output_center_y + 65, 1)
        connect("mux_or", "mux_output_F")
        connect("mux_or", "mux_not_F")
        connect("mux_not_F", "mux_output_Fbar")

        self._assign_wire_routes()
        self._error = ""
        self.changed.emit()
        self.schemeChanged.emit()

    def _set_error(self, message: str) -> None:
        self._error = message
        self.changed.emit()

    def _assign_wire_routes(self) -> None:
        nodes = {node["id"]: node for node in self._nodes}
        corridors: dict[tuple[float, float], list[dict[str, Any]]] = {}
        source_wires: dict[str, list[dict[str, Any]]] = {}
        target_wires: dict[str, list[dict[str, Any]]] = {}
        for wire in self._connections:
            source = nodes[wire["source"]]
            target = nodes[wire["target"]]
            corridor = (
                source["x"] + source["width"],
                target["x"],
            )
            corridors.setdefault(corridor, []).append(wire)
            source_wires.setdefault(wire["source"], []).append(wire)
            target_wires.setdefault(wire["target"], []).append(wire)

        for corridor_wires in corridors.values():
            ordered = sorted(
                corridor_wires,
                key=lambda wire: (
                    nodes[wire["source"]]["y"] + wire["sourceOffset"]
                    + nodes[wire["target"]]["y"] + wire["targetOffset"],
                    wire["source"],
                    wire["target"],
                ),
            )
            count = len(ordered)
            for index, wire in enumerate(ordered):
                wire["routeChannelFraction"] = (index + 1) / (count + 1)
                wire["routeLaneOffset"] = (
                    index - (count - 1) / 2
                ) * 24

        for connected_wires in source_wires.values():
            ordered = sorted(
                connected_wires,
                key=lambda wire: (
                    nodes[wire["target"]]["y"] + wire["targetOffset"],
                    wire["target"],
                ),
            )
            count = len(ordered)
            for index, wire in enumerate(ordered):
                wire["sourceRouteIndex"] = index
                wire["sourceOffset"] = 10 + (index + 1) * 80 / (count + 1)

        for connected_wires in target_wires.values():
            ordered = sorted(
                connected_wires,
                key=lambda wire: (
                    nodes[wire["source"]]["y"] + wire["sourceOffset"],
                    wire["source"],
                ),
            )
            count = len(ordered)
            for index, wire in enumerate(ordered):
                wire["targetRouteIndex"] = index
                wire["targetOffset"] = 10 + (index + 1) * 80 / (count + 1)

        bottom_lane_index = 0
        bottom_edge = max(
            (node["y"] + node["height"] for node in self._nodes), default=0
        )
        for wire in self._connections:
            wire.pop("wrapSide", None)
            wire.pop("wrapLaneY", None)
            source = nodes[wire["source"]]
            target = nodes[wire["target"]]
            route = _wire_route_points(wire, source, target)
            blocked = any(
                _path_intersects_node(route, node)
                for node in self._nodes
                if node["id"] not in (wire["source"], wire["target"])
            )
            if not blocked:
                continue

            lane_y = bottom_edge + 32 + bottom_lane_index * 24
            direction = 1 if target["x"] >= source["x"] + source["width"] else -1
            launch_x = (
                source["x"] + source["width"]
                + direction * (12 + wire["sourceRouteIndex"] * 6)
            )
            approach_x = (
                target["x"]
                - direction * (12 + wire["targetRouteIndex"] * 6)
            )
            candidate = [
                (source["x"] + source["width"],
                 source["y"] + wire["sourceOffset"]),
                (launch_x, source["y"] + wire["sourceOffset"]),
                (launch_x, lane_y),
                (approach_x, lane_y),
                (approach_x, target["y"] + wire["targetOffset"]),
                (target["x"], target["y"] + wire["targetOffset"]),
            ]
            if any(
                _path_intersects_node(candidate, node)
                for node in self._nodes
                if node["id"] not in (wire["source"], wire["target"])
            ):
                continue
            wire["wrapSide"] = "bottom"
            wire["wrapLaneY"] = lane_y
            bottom_lane_index += 1

        if self._connections:
            route_points = [
                point
                for wire in self._connections
                for point in _wire_route_points(
                    wire, nodes[wire["source"]], nodes[wire["target"]]
                )
            ]
            self._scheme_height = max(
                self._scheme_height,
                ceil(max(point[1] for point in route_points) + 20),
            )

    def _build_scheme(self) -> None:
        self._scheme_description = ""
        outputs = [output for output in self._outputs if output["hasResult"]]
        total_terms = sum(
            len(output["cubes"])
            for output in outputs
            if output["cubes"]
            and not all(bit is None for bit in output["cubes"][0])
        )
        self._scheme_height = max(
            700,
            120 * self._variable_count + 100,
            130 * max(1, total_terms) + 100,
        )
        self._scheme_width = 1020
        self._nodes = []
        self._connections = []
        self._node_positions = {}

        def add_node(node_id: str, label: str, kind: str, x: float, y: float) -> None:
            node = {"id": node_id, "label": label, "type": kind, "x": x, "y": y,
                    "width": 110, "height": 100, "maxInputs": 4}
            self._nodes.append(node)
            self._node_positions[node_id] = (x, y)

        def connect(source: str, target: str, source_offset: float, target_offset: float) -> None:
            self._connections.append({
                "source": source, "target": target,
                "sourceOffset": source_offset, "targetOffset": target_offset,
                "color": _wire_color(source),
            })

        nonconstant_outputs = [
            output for output in outputs
            if output["cubes"]
            and not all(bit is None for bit in output["cubes"][0])
        ]
        if nonconstant_outputs:
            variable_y = [
                40 + index * (self._scheme_height - 180)
                / max(1, self._variable_count - 1)
                for index in range(self._variable_count)
            ]
        else:
            variable_y = []

        all_cubes = [
            cube for output in nonconstant_outputs for cube in output["cubes"]
        ]
        if all_cubes:
            for index, variable in enumerate(VARIABLES[:self._variable_count]):
                add_node(
                    f"var_{variable}", variable, "INPUT", 20, variable_y[index]
                )

        has_negations = {
            variable
            for cube in all_cubes
            for offset, variable in enumerate(VARIABLES[:self._variable_count])
            if cube[offset] == 0
        }
        for index, variable in enumerate(VARIABLES[:self._variable_count]):
            if variable in has_negations:
                add_node(
                    f"not_{variable}", f"{variable}'", "NOT", 205, variable_y[index]
                )
                connect(f"var_{variable}", f"not_{variable}", 50, 50)

        term_id = 0
        for output_index, output in enumerate(outputs):
            output_name = output["name"]
            cubes = output["cubes"]
            output_y = min(
                self._scheme_height - 120,
                50 + output_index * (self._scheme_height - 160)
                / max(1, len(outputs) - 1),
            )
            if not cubes:
                constant_id = "constant" if output_name == "F" else f"constant_{output['id']}"
                add_node(
                    constant_id, f"{output_name} = 0", "CONSTANT", 820, output_y
                )
                continue
            if len(cubes) == 1 and all(bit is None for bit in cubes[0]):
                constant_id = "constant" if output_name == "F" else f"constant_{output['id']}"
                add_node(
                    constant_id, f"{output_name} = 1", "CONSTANT", 820, output_y
                )
                continue

            term_positions = []
            for cube_index, cube in enumerate(cubes):
                current_term_id = term_id
                gate_id = f"and_term_{term_id}"
                gate_y = 40 + term_id * 130
                term_id += 1
                term_positions.append((current_term_id, gate_y))
                literals = [
                    (index, variable, bit)
                    for index, (variable, bit) in enumerate(
                        zip(VARIABLES[:self._variable_count], cube)
                    )
                    if bit is not None
                ]
                label = (
                    f"AND  {output_name}" if len(cubes) == 1
                    else f"AND {output_name} term {cube_index + 1}"
                )
                add_node(gate_id, label, "AND", 445, gate_y)
                self._nodes[-1]["maxInputs"] = max(1, len(literals))
                for literal_index, variable, value in literals:
                    source = f"var_{variable}" if value else f"not_{variable}"
                    target_offset = 10 + (
                        len([item for item in literals if item[0] < literal_index]) + 1
                    ) * (80 / (len(literals) + 1))
                    connect(source, gate_id, 50, target_offset)

            if len(term_positions) > 1:
                output_gate_id = (
                    "or_output" if output_name == "F"
                    else f"or_{output['id']}"
                )
                output_gate_y = sum(y for _, y in term_positions) / len(term_positions)
                add_node(output_gate_id, f"OR  {output_name}", "OR", 785, output_gate_y)
                self._nodes[-1]["maxInputs"] = len(term_positions)
                for connection_index, (current_term_id, _) in enumerate(term_positions):
                    connect(
                        f"and_term_{current_term_id}",
                        output_gate_id,
                        50,
                        15 + (connection_index + 1) * 70
                        / (len(term_positions) + 1),
                    )

    @Slot(str)
    def exportPdf(self, path: str) -> None:
        if not self.hasScheme:
            self._error = "Generate a Boolean function or gate scheme before exporting the PDF."
            self.changed.emit()
            return
        if not path:
            self._error = "Choose a file path for the PDF export."
            self.changed.emit()
            return
        path = QUrl(path).toLocalFile() or path
        try:
            self._write_pdf(path)
        except (OSError, RuntimeError, ValueError) as error:
            self._error = f"Could not export PDF: {error}"
            self.changed.emit()
            return
        self._error = f"PDF exported to {path}"
        self.changed.emit()

    def _write_pdf(self, path: str) -> None:
        left, top, right, bottom = self._scheme_bounds()
        result_outputs = [
            output for output in self._outputs if output["hasResult"]
        ]
        result_panels = [
            panel for panel in self._table_panels if panel["hasResult"]
        ]
        page_width_mm = max(270.0, (right + 80) * 0.30)
        page_height_mm = max(
            210.0,
            (bottom + 550 + 110 * len(result_panels)
             + 300 * len(result_outputs)) * 0.30,
        )

        writer = QPdfWriter(path)
        writer.setResolution(144)
        writer.setPageLayout(QPageLayout(
            QPageSize(QSizeF(page_width_mm, page_height_mm), QPageSize.Millimeter),
            QPageLayout.Portrait, QMarginsF(12, 12, 12, 12),
        ))
        painter = QPainter(writer)
        if not painter.isActive():
            raise RuntimeError("The PDF painter could not be initialized.")

        page_width = writer.width()
        margin = 48
        painter.setPen(QColor("#17233b"))
        painter.setFont(QFont("Arial", 18, QFont.Bold))
        painter.drawText(margin, 48, "Boolean Logic Workbench")
        painter.setFont(QFont("Arial", 10))
        y = 82
        pdf_outputs = [] if self._scheme_description else result_outputs
        pdf_panels = [] if self._scheme_description else result_panels
        for output in pdf_outputs:
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.drawText(margin, y, f"Output {output['name']}")
            y += 18
            for title, value in (
                ("Canonical SOP", output["sop"]),
                ("Canonical POS", output["pos"]),
            ):
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(margin + 8, y, f"{title}:")
                painter.setFont(QFont("Arial", 8))
                y += 15
                y = self._draw_wrapped(
                    painter, value, margin + 16, y, page_width - margin * 2 - 16
                )
                y += 5

        headers = ["C/D", "A'B'", "A'B", "AB", "AB'"]
        col_width = 112
        if pdf_panels:
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(margin, y, "Truth table")
            y += 18
        for panel in pdf_panels:
            output_name = panel["outputName"]
            suffix = f" · {panel['assignment']}" if panel["assignment"] else ""
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(margin, y, f"{output_name}{suffix}")
            y += 15
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            for col, header in enumerate(headers):
                painter.drawText(margin + col * col_width, y, header)
            painter.setFont(QFont("Arial", 8))
            for row in panel["rows"]:
                y += 15
                cells = [row["label"]] + [
                    f"{cell['value']}(P{cell['index']})"
                    for cell in row["cells"]
                ]
                for col, cell in enumerate(cells):
                    painter.drawText(margin + col * col_width, y, cell)
            y += 10

        painter.setFont(QFont("Arial", 12, QFont.Bold))
        y += 30
        painter.drawText(margin, y, "Logical scheme")
        if self._scheme_description:
            painter.setFont(QFont("Arial", 9))
            y += 17
            painter.drawText(margin, y, self._scheme_description)
        scheme_y = y + 20
        available_width = page_width - margin * 2
        available_height = writer.height() - scheme_y - margin
        scheme_scale = min(
            available_width / max(1.0, right - left),
            available_height / max(1.0, bottom - top),
        )
        painter.save()
        painter.translate(margin, scheme_y)
        painter.scale(scheme_scale, scheme_scale)
        painter.translate(-left, -top)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        nodes_by_id = {node["id"]: node for node in self._nodes}
        for wire in self._connections:
            source = nodes_by_id[wire["source"]]
            target = nodes_by_id[wire["target"]]
            path_shape = QPainterPath()
            points = _wire_route_points(wire, source, target)
            path_shape.moveTo(*points[0])
            for point in points[1:]:
                path_shape.lineTo(*point)
            painter.setPen(QPen(QColor("#ffffff"), 6, Qt.SolidLine,
                                Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path_shape)
            painter.setPen(QPen(QColor(wire["color"]), 2.5, Qt.SolidLine,
                                Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path_shape)
        for node in self._nodes:
            rect = (node["x"], node["y"], node["width"], node["height"])
            painter.setPen(QPen(QColor("#315eaa"), 2))
            painter.setBrush(QColor("#f2f6ff"))
            painter.drawRoundedRect(*rect, 10, 10)
            self._draw_gate(painter, node)
            painter.setPen(QColor("#17233b"))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(node["x"] + 4, node["y"] + 78, node["width"] - 8, 20,
                             int(Qt.AlignCenter), node["label"])
        painter.restore()
        painter.end()

    def _scheme_bounds(self) -> tuple[float, float, float, float]:
        if not self._nodes:
            return 0.0, 0.0, 1.0, 1.0
        nodes_by_id = {node["id"]: node for node in self._nodes}
        wire_points = []
        for wire in self._connections:
            source = nodes_by_id[wire["source"]]
            target = nodes_by_id[wire["target"]]
            wire_points.extend(_wire_route_points(wire, source, target))
        wire_x = [point[0] for point in wire_points]
        wire_y = [point[1] for point in wire_points]
        return (
            min([node["x"] for node in self._nodes] + wire_x) - 4,
            min([node["y"] for node in self._nodes] + wire_y) - 4,
            max([node["x"] + node["width"] for node in self._nodes] + wire_x) + 4,
            max([node["y"] + node["height"] for node in self._nodes] + wire_y) + 4,
        )

    def _draw_gate(self, painter: QPainter, node: dict[str, Any]) -> None:
        x, y = node["x"], node["y"]
        kind = node["type"]
        incoming = [wire for wire in self._connections if wire["target"] == node["id"]]
        if kind in {"AND", "OR", "NOT", "OUTPUT"}:
            for wire in incoming:
                pin_y = y + wire["targetOffset"]
                painter.setPen(QPen(QColor(wire["color"]), 2.5))
                painter.drawLine(x, pin_y, x + 25, pin_y)
        output_start = x + (
            84 if kind == "NOT"
            else 78 if kind == "INPUT"
            else 79 if kind == "CONSTANT"
            else 78
        )
        for wire in self._connections:
            if wire["source"] == node["id"]:
                painter.setPen(QPen(QColor(wire["color"]), 2.5))
                painter.drawLine(
                    output_start,
                    y + wire["sourceOffset"],
                    x + node["width"],
                    y + wire["sourceOffset"],
                )

        painter.setBrush(QColor("#ffffff"))
        if kind == "AND":
            shape = QPainterPath()
            shape.moveTo(x + 25, y + 20)
            shape.lineTo(x + 51, y + 20)
            shape.cubicTo(x + 86, y + 20, x + 86, y + 72, x + 51, y + 72)
            shape.lineTo(x + 25, y + 72)
            shape.closeSubpath()
            painter.drawPath(shape)
        elif kind == "OR":
            shape = QPainterPath()
            shape.moveTo(x + 25, y + 18)
            shape.cubicTo(x + 48, y + 20, x + 67, y + 30, x + 85, y + 50)
            shape.cubicTo(x + 67, y + 70, x + 48, y + 80, x + 25, y + 82)
            shape.cubicTo(x + 36, y + 62, x + 36, y + 38, x + 25, y + 18)
            shape.closeSubpath()
            painter.drawPath(shape)
        elif kind == "NOT":
            shape = QPainterPath()
            shape.moveTo(x + 29, y + 24)
            shape.lineTo(x + 73, y + 50)
            shape.lineTo(x + 29, y + 76)
            shape.closeSubpath()
            painter.drawPath(shape)
            painter.drawEllipse(x + 72, y + 44, 12, 12)
        elif kind == "INPUT":
            painter.drawEllipse(x + 34, y + 28, 42, 42)
        elif kind == "OUTPUT":
            painter.drawLine(x + 25, y + 50, x + 70, y + 50)
            painter.drawEllipse(x + 70, y + 43, 14, 14)
        else:
            painter.drawRoundedRect(x + 27, y + 22, 56, 50, 7, 7)

    @staticmethod
    def _draw_wrapped(painter: QPainter, text: str, x: int, y: int, width: int,
                      line_spacing: int = 14) -> int:
        words = text.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and painter.fontMetrics().horizontalAdvance(candidate) > width:
                painter.drawText(x, y, line)
                y += line_spacing
                line = word
            else:
                line = candidate
        if line:
            painter.drawText(x, y, line)
            y += line_spacing
        return y
