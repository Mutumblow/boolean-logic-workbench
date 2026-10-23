import unittest

from logic import (
    BooleanLogic,
    _path_intersects_node,
    _wire_route_points,
    format_pos,
    format_sop,
    minimize_sop,
    parse_pos,
    parse_sop,
    expand_cubes,
    truth_table,
)


class CanonicalFormTests(unittest.TestCase):
    def test_sop_primes_map_to_zero_bits(self):
        self.assertEqual(parse_sop("A'B'C'D' + A'B'CD"), {0, 3})

    def test_parenthesized_sop_terms_and_whitespace(self):
        self.assertEqual(parse_sop("(A' B' C' D') + (A' B' C D)"), {0, 3})

    def test_abbreviated_products_expand_omitted_variables(self):
        self.assertEqual(
            parse_sop("A'B'C'D'+A'B+B'D'"),
            {0, 2, 4, 5, 6, 7, 8, 10},
        )
        self.assertEqual(parse_sop("A"), set(range(8, 16)))

    def test_minimized_sop_cubes_preserve_function(self):
        minterms = parse_sop("A'B'C'D'+A'B+B'D'")
        cubes = minimize_sop(minterms)
        self.assertEqual(expand_cubes(cubes), minterms)
        self.assertEqual(len(cubes), 2)

    def test_pos_clauses_map_to_zero_rows(self):
        self.assertEqual(
            parse_pos("(A+B+C+D) · (A+B+C+D')"),
            {0, 1},
        )

    def test_index_notation(self):
        self.assertEqual(parse_sop("Σm(0, 3, 15)"), {0, 3, 15})
        self.assertEqual(parse_pos("ΠM(1, 2, 8)"), {1, 2, 8})

    def test_canonical_form_round_trip(self):
        minterms = {0, 2, 5, 9, 15}
        self.assertEqual(parse_sop(format_sop(minterms)), minterms)
        zeros = set(range(16)) - minterms
        self.assertEqual(parse_pos(format_pos(zeros)), zeros)
        self.assertEqual(format_pos(zeros), "ΠP(1, 3, 4, 6, 7, 8, 10, 11, 12, 13, 14)")
        self.assertEqual(parse_pos("ΠP(1, 3, 5)"), {1, 3, 5})

    def test_constant_forms(self):
        self.assertEqual(parse_sop("0"), set())
        self.assertEqual(parse_sop("1"), set(range(16)))
        self.assertEqual(parse_pos("1"), set())
        self.assertEqual(parse_pos("0"), set(range(16)))
        self.assertEqual(format_sop(set()), "0")
        self.assertEqual(format_pos(set()), "1")

    def test_invalid_noncanonical_terms_are_rejected(self):
        for expression in ("A'B'C'D' + X", "A'B'B'D'"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    parse_sop(expression)
        with self.assertRaises(ValueError):
            parse_pos("(A+B+C)")


class TruthTableTests(unittest.TestCase):
    def test_rows_and_columns_use_requested_gray_order(self):
        rows = truth_table({0, 3})
        self.assertEqual([row["label"] for row in rows], ["C'D'", "C'D", "CD", "CD'"])
        self.assertEqual([row["values"] for row in rows], [
            [1, 0, 0, 0],
            [0, 0, 0, 0],
            [1, 0, 0, 0],
            [0, 0, 0, 0],
        ])
        self.assertEqual(
            [[cell["index"] for cell in row["cells"]] for row in rows],
            [[0, 4, 12, 8], [1, 5, 13, 9], [3, 7, 15, 11], [2, 6, 14, 10]],
        )


class ViewModelTests(unittest.TestCase):
    def test_calculation_builds_all_four_representations(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D' + A'B'CD")
        self.assertTrue(model.hasResult)
        self.assertEqual(model.sop, "A'B'C'D' + A'B'CD")
        self.assertTrue(model.pos.startswith("ΠP("))
        self.assertEqual(len(model.tableRows), 4)
        self.assertTrue(any(node["type"] == "AND" for node in model.schemeNodes))
        self.assertTrue(any(node["type"] == "OR" for node in model.schemeNodes))

    def test_input_sop_builds_three_product_gates_and_one_or(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D'+A'B+B'D'")
        and_gates = [node for node in model.schemeNodes if node["type"] == "AND"]
        or_gates = [node for node in model.schemeNodes if node["type"] == "OR"]
        self.assertEqual(len(and_gates), 3)
        self.assertEqual(len(or_gates), 1)
        self.assertEqual(
            sorted(sum(wire["target"] == gate["id"] for wire in model.connections)
                   for gate in and_gates),
            [2, 2, 4],
        )
        colors_by_source = {}
        for wire in model.connections:
            colors_by_source.setdefault(wire["source"], set()).add(wire["color"])
        self.assertTrue(all(len(colors) == 1 for colors in colors_by_source.values()))
        self.assertGreater(len({next(iter(colors)) for colors in colors_by_source.values()}), 1)
        for corridor in {
            (wire["source"], wire["target"])
            for wire in model.connections
        }:
            wire = next(
                connection for connection in model.connections
                if (connection["source"], connection["target"]) == corridor
            )
            self.assertIn("routeChannelFraction", wire)
            self.assertIn("routeLaneOffset", wire)
            self.assertIn("sourceRouteIndex", wire)
            self.assertIn("targetRouteIndex", wire)

        and_to_or = [
            wire for wire in model.connections if wire["target"] == "or_output"
        ]
        self.assertEqual(
            len({wire["routeChannelFraction"] for wire in and_to_or}),
            len(and_to_or),
        )
        nodes = {node["id"]: node for node in model.schemeNodes}
        self.assertTrue(any(wire.get("wrapSide") for wire in model.connections))
        for wire in model.connections:
            route = _wire_route_points(
                wire, nodes[wire["source"]], nodes[wire["target"]]
            )
            self.assertFalse(any(
                _path_intersects_node(route, node)
                for node in model.schemeNodes
                if node["id"] not in (wire["source"], wire["target"])
            ))

    def test_dense_schemes_keep_each_source_signal_distinguishable(self):
        model = BooleanLogic()
        model.calculate("SOP", "Sigma m(" + ", ".join(map(str, range(16))) + ")")
        colors_by_source = {
            wire["source"]: wire["color"] for wire in model.connections
        }
        self.assertEqual(len(colors_by_source), 24)
        self.assertEqual(len(set(colors_by_source.values())), len(colors_by_source))
        nodes = {node["id"]: node for node in model.schemeNodes}
        for wire in model.connections:
            route = _wire_route_points(
                wire, nodes[wire["source"]], nodes[wire["target"]]
            )
            self.assertFalse(any(
                _path_intersects_node(route, node)
                for node in model.schemeNodes
                if node["id"] not in (wire["source"], wire["target"])
            ))

        fanout_offsets = {}
        for wire in model.connections:
            fanout_offsets.setdefault(wire["source"], []).append(
                wire["sourceOffset"]
            )
        self.assertTrue(all(
            min(b - a for a, b in zip(sorted(offsets), sorted(offsets)[1:]))
            >= 8
            for offsets in fanout_offsets.values()
            if len(offsets) > 1
        ))
        wrapped_lanes = sorted(
            wire["wrapLaneY"] for wire in model.connections if wire.get("wrapSide")
        )
        self.assertTrue(all(
            second - first >= 24
            for first, second in zip(wrapped_lanes, wrapped_lanes[1:])
        ))
        self.assertGreaterEqual(
            model.schemeHeight,
            max(
                point[1]
                for wire in model.connections
                for point in _wire_route_points(
                    wire, nodes[wire["source"]], nodes[wire["target"]]
                )
            ) + 20,
        )

    def test_invalid_input_does_not_replace_last_valid_result(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D'")
        previous_sop = model.sop
        model.calculate("SOP", "not a canonical form")
        self.assertTrue(model.hasResult)
        self.assertEqual(model.sop, previous_sop)
        self.assertTrue(model.error)

    def test_table_cells_are_editable_and_update_forms_and_scheme(self):
        model = BooleanLogic()
        model.setTableCell(4, 1)
        self.assertTrue(model.hasResult)
        self.assertEqual(model.sop, "A'BC'D'")
        self.assertEqual(model.pos, "ΠP(0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)")
        cell = next(
            cell for row in model.tableRows for cell in row["cells"]
            if cell["index"] == 4
        )
        self.assertEqual(cell["value"], 1)
        self.assertTrue(any(node["id"] == "and_term_0" for node in model.schemeNodes))

        model.setTableCell(4, 0)
        self.assertEqual(model.sop, "0")
        model.clearTable()
        self.assertEqual(model.sop, "0")

    def test_pos_input_generates_the_same_sop_based_scheme(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D' + A'B'CD")
        sop_nodes = [(node["id"], node["type"], node["label"])
                     for node in model.schemeNodes]
        model.calculate("POS", "ΠP(1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)")
        pos_nodes = [(node["id"], node["type"], node["label"])
                     for node in model.schemeNodes]
        self.assertEqual(pos_nodes, sop_nodes)
        self.assertEqual(model._minterms, {0, 3})

    def test_dragging_updates_node_and_keeps_it_inside_canvas(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D'")
        original_bounds = model._scheme_bounds()
        model.moveNode("and_term_0", 10_000, 10_000)
        node = next(node for node in model.schemeNodes if node["id"] == "and_term_0")
        self.assertEqual(node["x"] + node["width"], model.schemeWidth)
        self.assertEqual(node["y"] + node["height"], model.schemeHeight)
        left, top, right, bottom = model._scheme_bounds()
        self.assertLessEqual(left, min(item["x"] for item in model.schemeNodes))
        self.assertGreaterEqual(right, max(
            item["x"] + item["width"] for item in model.schemeNodes
        ))
        self.assertLessEqual(top, min(item["y"] for item in model.schemeNodes))
        self.assertGreaterEqual(bottom, max(
            item["y"] + item["height"] for item in model.schemeNodes
        ))
        self.assertNotEqual((left, top, right, bottom), original_bounds)

    def test_add_gates_and_connect_custom_scheme(self):
        model = BooleanLogic()
        model.addGate("INPUT", "X")
        model.addGate("INPUT", "Y")
        model.addGate("AND", "")
        model.addGate("OUTPUT", "F")

        model.connectNodes("custom_1", "custom_3")
        model.connectNodes("custom_2", "custom_3")
        model.connectNodes("custom_3", "custom_4")

        self.assertEqual(len(model.connections), 3)
        self.assertTrue(all(
            "routeChannelFraction" in wire
            and "routeLaneOffset" in wire
            and "sourceRouteIndex" in wire
            and "targetRouteIndex" in wire
            for wire in model.connections
        ))
        self.assertEqual(
            [(node["type"], node["label"]) for node in model.schemeNodes],
            [("INPUT", "X"), ("INPUT", "Y"), ("AND", "AND1"), ("OUTPUT", "F")],
        )

    def test_custom_scheme_rejects_loops_and_invalid_targets(self):
        model = BooleanLogic()
        model.addGate("AND", "")
        model.addGate("AND", "")
        model.addGate("OUTPUT", "F")
        model.connectNodes("custom_1", "custom_2")
        model.connectNodes("custom_2", "custom_1")
        self.assertIn("loop", model.error)
        self.assertEqual(len(model.connections), 1)

        model.connectNodes("custom_3", "custom_2")
        self.assertIn("source", model.error)
        self.assertEqual(len(model.connections), 1)


if __name__ == "__main__":
    unittest.main()
