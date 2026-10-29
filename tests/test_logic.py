import unittest

from logic import (
    BooleanLogic,
    _path_intersects_node,
    _wire_route_points,
    infer_variable_count,
    format_pos,
    format_sop,
    minimize_sop,
    parse_pos,
    parse_sop,
    parse_sop_cubes,
    expand_cubes,
    truth_table,
    truth_table_panels,
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

    def test_variable_count_is_inferred_from_literals_and_indices(self):
        self.assertEqual(infer_variable_count("A'B'C'D'E'"), 5)
        self.assertEqual(infer_variable_count("A'B'C'D'E'F'G'H'"), 8)
        self.assertEqual(infer_variable_count("Σm(0, 16, 31)"), 5)

    def test_eight_variable_forms_parse_and_round_trip(self):
        variables = "ABCDEFGH"
        expression = "A'B'C'D'E'F'G'H' + ABCDEFGH"
        cubes = parse_sop_cubes(expression, variables)
        minterms = expand_cubes(cubes)
        self.assertEqual(minterms, {0, 255})
        self.assertEqual(expand_cubes(minimize_sop(minterms, 8)), minterms)
        self.assertEqual(
            parse_sop(format_sop(minterms, variables), variables),
            minterms,
        )
        self.assertEqual(parse_pos("ΠP(0, 255)", variables), {0, 255})


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

    def test_extra_variable_tables_are_sliced_by_fixed_assignment(self):
        panels = truth_table_panels({0, 1, 31}, 5)
        self.assertEqual([panel["assignment"] for panel in panels], ["E=0", "E=1"])
        self.assertEqual(panels[0]["rows"][0]["cells"][0], {"index": 0, "value": 1})
        self.assertEqual(panels[1]["rows"][0]["cells"][0], {"index": 1, "value": 1})
        self.assertEqual(panels[1]["rows"][2]["cells"][2], {"index": 31, "value": 1})


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
        model.calculate("SOP", "   ")
        self.assertEqual(model.sop, previous_sop)
        self.assertIn("Enter a canonical form", model.error)
        model.calculate("SOP", "Σm(0, 511)")
        self.assertEqual(model.sop, previous_sop)
        self.assertIn("supports up to 8 variables", model.error)

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

    def test_multi_output_functions_have_independent_tables_and_scheme(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D'E'F' + ABCDEF")
        self.assertEqual(model.variableCount, 6)
        self.assertEqual(len(model.tablePanels), 4)
        self.assertEqual(
            [panel["assignment"] for panel in model.tablePanels],
            ["E=0, F=0", "E=0, F=1", "E=1, F=0", "E=1, F=1"],
        )

        model.addOutput("Y0")
        model.calculate("SOP", "A'B'C'D'EF' + ABCDEF")
        self.assertEqual(model.variableCount, 6)
        self.assertEqual(len(model.tablePanels), 8)
        self.assertEqual(model.activeOutputName, "Y0")
        self.assertTrue(any(
            node["label"] == "OR  F" for node in model.schemeNodes
        ))
        self.assertTrue(any(
            node["label"] == "OR  Y0" for node in model.schemeNodes
        ))

        original_sop = model.sop
        model.setOutputTableCell("F", 1, 1)
        self.assertEqual(model.sop, original_sop)
        model.selectOutput("F")
        self.assertNotEqual(model.sop, original_sop)
        self.assertEqual(model.variableCount, 6)

    def test_removing_high_variable_output_shrinks_table_slices(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C'D'E'")
        model.addOutput("Y0")
        model.calculate("SOP", "A'B'C'D'E'F'G'H'")
        self.assertEqual(model.variableCount, 8)
        self.assertEqual(len(model.tablePanels), 32)
        model.removeActiveOutput()
        self.assertEqual(model.activeOutputName, "F")
        self.assertEqual(model.variableCount, 5)
        self.assertEqual(len(model.tablePanels), 2)

    def test_shorter_output_forms_expand_across_shared_variables(self):
        model = BooleanLogic()
        model.calculate("POS", "(A+B+C+D)")
        model.addOutput("Y0")
        model.calculate("SOP", "A'B'C'D'E'")
        self.assertEqual(model.variableCount, 5)
        expected = {
            (minterm << 1) | suffix
            for minterm in range(1, 16)
            for suffix in (0, 1)
        }
        self.assertEqual(model._outputs[0]["minterms"], expected)

    def test_four_to_one_mux_function_uses_six_variables(self):
        model = BooleanLogic()
        model.calculate("SOP", "A'B'C + A'BD + AB'E + ABF")
        self.assertEqual(model.variableCount, 6)
        self.assertEqual(len(model.tablePanels), 4)
        self.assertEqual(
            sum(node["type"] == "AND" for node in model.schemeNodes), 4
        )
        self.assertEqual(
            sum(node["type"] == "OR" for node in model.schemeNodes), 1
        )

    def test_mux_synthesizer_requires_a_calculated_function(self):
        model = BooleanLogic()
        model.generateMultiplexer()
        self.assertIn("Enter or calculate f", model.error)
        self.assertFalse(model.hasScheme)

    def test_mux_scheme_decomposes_arbitrary_function(self):
        model = BooleanLogic()
        model.calculate(
            "SOP",
            "A'B'C'D'+A'B'CD+A'BC'D+AB'CD'+ABC'D'",
        )
        expected_minterms = set(model._minterms)
        model.generateMultiplexer()

        nodes = {node["id"]: node for node in model.schemeNodes}
        self.assertTrue(model.hasScheme)
        self.assertTrue(model.hasAnyResult)
        self.assertIn("decomposition of the selected f", model.schemeDescription)
        self.assertEqual(sum(node["type"] == "INPUT" for node in nodes.values()), 4)
        self.assertEqual(sum(node["type"] == "AND" for node in nodes.values()), 9)
        self.assertEqual(sum(node["type"] == "OR" for node in nodes.values()), 2)
        self.assertEqual(sum(node["type"] == "NOT" for node in nodes.values()), 5)
        self.assertEqual(sum(node["type"] == "OUTPUT" for node in nodes.values()), 2)

        branch_sources = {
            "mux_select_term_I3": {
                "mux_data_I3_or", "mux_not_A", "mux_not_B",
            },
            "mux_select_term_I2": {
                "mux_data_I2_term_0", "mux_not_A", "mux_var_B",
            },
            "mux_select_term_I1": {
                "mux_data_I1_term_0", "mux_var_A", "mux_not_B",
            },
            "mux_select_term_I0": {
                "mux_data_I0_term_0", "mux_var_A", "mux_var_B",
            },
        }
        for target, expected_sources in branch_sources.items():
            self.assertEqual({
                wire["source"] for wire in model.connections
                if wire["target"] == target
            }, expected_sources)
        self.assertEqual({
            wire["source"] for wire in model.connections
            if wire["target"] == "mux_output_F"
        }, {"mux_or"})
        self.assertEqual({
            wire["source"] for wire in model.connections
            if wire["target"] == "mux_not_F"
        }, {"mux_or"})
        self.assertEqual({
            wire["source"] for wire in model.connections
            if wire["target"] == "mux_output_Fbar"
        }, {"mux_not_F"})

        def evaluate(node_id, assignment):
            node = nodes[node_id]
            if node["type"] == "INPUT":
                return assignment[node["label"]]
            if node["type"] == "CONSTANT":
                return int(node["label"])
            sources = [
                wire["source"] for wire in model.connections
                if wire["target"] == node_id
            ]
            values = [evaluate(source, assignment) for source in sources]
            if node["type"] == "NOT":
                return 1 - values[0]
            if node["type"] == "AND":
                return int(all(values))
            if node["type"] == "OR":
                return int(any(values))
            if node["type"] == "OUTPUT":
                return values[0]
            self.fail(f"Unexpected gate type: {node['type']}")

        for index in range(16):
            assignment = {
                variable: (index >> (3 - offset)) & 1
                for offset, variable in enumerate("ABCD")
            }
            self.assertEqual(
                evaluate("mux_output_F", assignment),
                int(index in expected_minterms),
            )
            self.assertEqual(
                evaluate("mux_output_Fbar", assignment),
                int(index not in expected_minterms),
            )

        for wire in model.connections:
            route = _wire_route_points(
                wire, nodes[wire["source"]], nodes[wire["target"]]
            )
            self.assertFalse(any(
                _path_intersects_node(route, node)
                for node in nodes.values()
                if node["id"] not in (wire["source"], wire["target"])
            ))

    def test_mux_scheme_supports_constant_functions(self):
        for constant in ("0", "1"):
            with self.subTest(constant=constant):
                model = BooleanLogic()
                model.calculate("SOP", constant)
                model.generateMultiplexer()
                self.assertEqual(
                    sum(node["type"] == "CONSTANT" for node in model.schemeNodes),
                    4,
                )
                self.assertEqual(len(model.connections), 21)

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
