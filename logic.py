import re
from math import ceil
from typing import Any

from PySide6.QtCore import QMarginsF, QObject, Property, QUrl, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor, QFont, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen,
)
from PySide6.QtCore import QSizeF


VARIABLES = "ABCD"
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
        color_index = len(VARIABLES) * 2 + int(source_id[9:])
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


def _index_from_literals(tokens: list[tuple[str, bool]], *, product: bool) -> int:
    names = [name for name, _ in tokens]
    if sorted(names) != sorted(VARIABLES):
        raise ValueError("Each canonical term must contain A, B, C, and D exactly once.")

    bits: dict[str, int] = {}
    for name, negated in tokens:
        bits[name] = int(not negated) if product else int(negated)
    return sum(bits[name] << (3 - offset) for offset, name in enumerate(VARIABLES))


def _parse_literals(text: str, *, product: bool) -> list[tuple[str, bool]]:
    if product:
        parts = re.findall(r"([A-D])\s*('?)", text)
        if re.sub(r"\s+", "", "".join(name + prime for name, prime in parts)) != re.sub(
            r"\s+", "", text
        ):
            raise ValueError(f"Invalid literal in canonical term: {text!r}.")
        return [(name, bool(prime)) for name, prime in parts]

    parts = re.split(r"\s*\+\s*", text.strip())
    tokens: list[tuple[str, bool]] = []
    for part in parts:
        match = re.fullmatch(r"\s*([A-D])\s*('?)\s*", part)
        if match is None:
            raise ValueError(f"Invalid literal in canonical term: {part!r}.")
        tokens.append((match.group(1), bool(match.group(2))))
    return tokens


def parse_sop_cubes(text: str) -> list[Cube]:
    source = text.strip()
    if source in {"0", "1"}:
        return [] if source == "0" else [(None, None, None, None)]

    shorthand = re.fullmatch(r"(?:Σ|Sigma)\s*m\s*\(([^)]*)\)", source, re.IGNORECASE)
    if shorthand:
        values = shorthand.group(1).strip()
        if not values:
            return set()
        try:
            indices = [int(value.strip()) for value in values.split(",")]
        except ValueError as error:
            raise ValueError("Minterm indices must be integers from 0 to 15.") from error
        if any(index < 0 or index > 15 for index in indices):
            raise ValueError("Minterm indices must be from 0 to 15.")
        return [
            tuple((index >> (3 - offset)) & 1 for offset in range(4))
            for index in sorted(set(indices))
        ]

    terms = re.split(r"\s*\+\s*", source)
    if not terms or any(not term.strip() for term in terms):
        raise ValueError("Enter a sum of canonical products, such as A'B'C'D' + A'B'CD.")
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
        cubes.append(tuple(assigned_bits.get(name) for name in VARIABLES))
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
            minterms.add(sum(int(bit) << (3 - offset) for offset, bit in enumerate(bits)))
    return minterms


def parse_sop(text: str) -> set[int]:
    return expand_cubes(parse_sop_cubes(text))


def minimize_sop(minterms: set[int]) -> list[Cube]:
    if not minterms:
        return []
    if len(minterms) == 16:
        return [(None, None, None, None)]

    current = {tuple((index >> (3 - offset)) & 1 for offset in range(4))
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
            if all(bit is None or bit == ((index >> (3 - offset)) & 1)
                   for offset, bit in enumerate(cube))
        }
        covers.append(covered)

    target_mask = sum(1 << index for index in minterms)
    cover_masks = [
        sum(1 << index for index in covered) for covered in covers
    ]
    best: dict[int, tuple[int, ...]] = {0: ()}
    for prime_index, cover_mask in enumerate(cover_masks):
        for covered_mask, selection in list(best.items()):
            merged_mask = covered_mask | cover_mask
            candidate = selection + (prime_index,)
            previous = best.get(merged_mask)
            candidate_cost = (
                len(candidate),
                sum(sum(bit is not None for bit in prime_list[i]) for i in candidate),
            )
            if previous is None or candidate_cost < (
                len(previous),
                sum(sum(bit is not None for bit in prime_list[i]) for i in previous),
            ):
                best[merged_mask] = candidate

    return [prime_list[index] for index in best[target_mask]]


def parse_pos(text: str) -> set[int]:
    source = text.strip()
    if source in {"0", "1"}:
        return set(range(16)) if source == "0" else set()

    shorthand = re.fullmatch(r"(?:Π|Pi)\s*(?:M|P)\s*\(([^)]*)\)", source, re.IGNORECASE)
    if shorthand:
        values = shorthand.group(1).strip()
        if not values:
            return set()
        try:
            indices = [int(value.strip()) for value in values.split(",")]
        except ValueError as error:
            raise ValueError("Maxterm indices must be integers from 0 to 15.") from error
        if any(index < 0 or index > 15 for index in indices):
            raise ValueError("Maxterm indices must be from 0 to 15.")
        return set(indices)

    clauses = re.findall(r"\(([^()]*)\)", source)
    remainder = re.sub(r"\([^()]*\)", "", source)
    if not clauses or remainder.strip(" \t\r\n·*."):
        raise ValueError("Enter a product of canonical sums, such as (A+B+C+D)(A+B+C+D').")

    zero_indices: set[int] = set()
    for clause in clauses:
        zero_indices.add(_index_from_literals(_parse_literals(clause, product=False), product=False))
    return zero_indices


def _literal(name: str, bit: int) -> str:
    return name if bit else f"{name}'"


def format_sop(minterms: set[int]) -> str:
    if not minterms:
        return "0"
    if len(minterms) == 16:
        return "1"
    terms = []
    for index in sorted(minterms):
        terms.append("".join(_literal(name, (index >> (3 - offset)) & 1)
                             for offset, name in enumerate(VARIABLES)))
    return " + ".join(terms)


def format_pos(zero_indices: set[int]) -> str:
    if not zero_indices:
        return "1"
    if len(zero_indices) == 16:
        return "0"
    indices = ", ".join(str(index) for index in sorted(zero_indices))
    return f"ΠP({indices})"


def truth_table(minterms: set[int]) -> list[dict[str, Any]]:
    rows = []
    for cd in GRAY_ORDER:
        row_values = []
        cells = []
        for ab in GRAY_ORDER:
            index = (ab << 2) | cd
            value = int(index in minterms)
            row_values.append(value)
            cells.append({"index": index, "value": value})
        rows.append({
            "label": "".join(_literal(name, (cd >> (1 - offset)) & 1)
                             for offset, name in enumerate("CD")),
            "values": row_values,
            "cells": cells,
        })
    return rows


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
        self._nodes: list[dict[str, Any]] = []
        self._connections: list[dict[str, Any]] = []
        self._scheme_width = 1000
        self._scheme_height = 620
        self._node_positions: dict[str, tuple[float, float]] = {}
        self._scheme_cubes: list[Cube] = []

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @Property(bool, notify=changed)
    def hasResult(self) -> bool:
        return self._has_result

    @Property(str, notify=changed)
    def sop(self) -> str:
        return self._sop

    @Property(str, notify=changed)
    def pos(self) -> str:
        return self._pos

    @Property("QVariantList", notify=changed)
    def tableRows(self) -> list[dict[str, Any]]:
        return self._rows

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

    @Slot(str, str)
    def calculate(self, mode: str, text: str) -> None:
        try:
            if mode == "SOP":
                cubes = parse_sop_cubes(text)
                minterms = expand_cubes(cubes)
            elif mode == "POS":
                minterms = set(range(16)) - parse_pos(text)
                cubes = minimize_sop(minterms)
            else:
                raise ValueError("Choose either canonical SOP or canonical POS input.")
        except ValueError as error:
            self._error = str(error)
            self.changed.emit()
            return

        self._apply_function(minterms, cubes)

    @Slot(int, int)
    def setTableCell(self, index: int, value: int) -> None:
        if not 0 <= index < 16:
            self._set_error("Truth-table cells must have P indices from 0 to 15.")
            return
        if value not in (0, 1):
            self._set_error("Truth-table cell values must be 0 or 1.")
            return
        minterms = set(self._minterms)
        if value:
            minterms.add(index)
        else:
            minterms.discard(index)
        self._apply_function(minterms)

    @Slot()
    def clearTable(self) -> None:
        self._apply_function(set())

    def _apply_function(
        self, minterms: set[int], cubes: list[Cube] | None = None
    ) -> None:
        self._minterms = minterms
        self._scheme_cubes = cubes if cubes is not None else minimize_sop(minterms)
        self._sop = format_sop(minterms)
        self._pos = format_pos(set(range(16)) - minterms)
        self._rows = truth_table(minterms)
        self._error = ""
        self._has_result = True
        self._build_scheme()
        self._assign_wire_routes()
        self.changed.emit()
        self.schemeChanged.emit()

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
        cubes = self._scheme_cubes
        self._scheme_height = max(700, 160 * max(1, len(cubes)) + 100)
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

        if not cubes:
            add_node("constant", "F = 0", "CONSTANT", 450, self._scheme_height / 2 - 50)
            return

        if len(cubes) == 1 and all(bit is None for bit in cubes[0]):
            add_node("constant", "F = 1", "CONSTANT", 450, self._scheme_height / 2 - 50)
            return

        variable_y = [self._scheme_height / 2 + (index - 1.5) * 110 - 50
                      for index in range(4)]
        for index, variable in enumerate(VARIABLES):
            add_node(f"var_{variable}", variable, "INPUT", 20, variable_y[index])

        has_negations = {
            variable for cube in cubes
            for offset, variable in enumerate(VARIABLES)
            if cube[offset] == 0
        }
        for index, variable in enumerate(VARIABLES):
            if variable in has_negations:
                add_node(f"not_{variable}", f"{variable}'", "NOT", 205, variable_y[index])
                connect(f"var_{variable}", f"not_{variable}", 50, 50)

        gate_x = 445
        for term_index, cube in enumerate(cubes):
            gate_id = f"and_term_{term_index}"
            gate_y = 40 + term_index * 160
            literals = [(index, variable, bit)
                        for index, (variable, bit) in enumerate(zip(VARIABLES, cube))
                        if bit is not None]
            add_node(gate_id, f"AND term {term_index + 1}", "AND", gate_x, gate_y)
            self._nodes[-1]["maxInputs"] = max(1, len(literals))
            for literal_index, variable, value in literals:
                source = f"var_{variable}" if value else f"not_{variable}"
                target_offset = 10 + (len([item for item in literals
                                           if item[0] < literal_index]) + 1) * (
                    80 / (len(literals) + 1)
                )
                connect(source, gate_id, 50, target_offset)

        if len(cubes) > 1:
            output_y = self._scheme_height / 2 - 50
            add_node("or_output", "OR  F", "OR", 785, output_y)
            self._nodes[-1]["maxInputs"] = len(cubes)
            for term_index in range(len(cubes)):
                connect(f"and_term_{term_index}", "or_output", 50,
                        15 + (term_index + 1) * 70 / (len(cubes) + 1))
        else:
            self._nodes[-1]["label"] = "AND  F"

    @Slot(str)
    def exportPdf(self, path: str) -> None:
        if not self._has_result:
            self._error = "Calculate a Boolean function before exporting the PDF."
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
        page_width_mm = max(270.0, (right + 80) * 0.30)
        page_height_mm = max(210.0, (bottom + 550) * 0.30)

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
        for title, value in (("Canonical SOP", self._sop), ("Canonical POS", self._pos)):
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.drawText(margin, y, f"{title}:")
            painter.setFont(QFont("Arial", 9))
            y += 20
            y = self._draw_wrapped(painter, value, margin + 8, y, page_width - margin * 2 - 8)
            y += 8

        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(margin, y, "Truth table")
        y += 18
        headers = ["C/D", "A'B'", "A'B", "AB", "AB'"]
        col_width = 112
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        for col, header in enumerate(headers):
            painter.drawText(margin + col * col_width, y, header)
        painter.setFont(QFont("Arial", 9))
        for row_index, row in enumerate(self._rows):
            y += 18
            cells = [row["label"]] + [
                f"{cell['value']}(P{cell['index']})" for cell in row["cells"]
            ]
            for col, cell in enumerate(cells):
                painter.drawText(margin + col * col_width, y, cell)

        painter.setFont(QFont("Arial", 12, QFont.Bold))
        y += 30
        painter.drawText(margin, y, "Logical scheme")
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
        if kind in {"AND", "OR", "NOT"}:
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
