"""
Full pytest suite for test_generation/path_finder.py (PathFinder).

PathFinder explores a chatbot's graph with a DFS that:
  - guarantees GLOBAL EDGE coverage (self.global_visited_edges, shared across the whole
    run), not full path coverage -- every edge is tested at least once, cycles don't
    cause infinite/duplicate re-exploration;
  - detects CYCLES per path (the `visited` set, local to the current DFS branch) and
    closes them with an escape route to a leaf node instead of leaving the simulated
    conversation open;
  - also uses the escape route when a node is reached a second time (via a different
    parent) after all of ITS OWN outgoing edges are already globally covered -- this is
    a different situation from a cycle, and the test suite keeps the two separate.

Fixtures build the (nodes_dict, adj_dict, nx_graph) triple PathFinder's constructor
expects, by hand, the same way the existing test file already did -- no Parser involved,
so each graph shape is controlled exactly.
"""

import pytest
import networkx as nx
from test_generation.path_finder import PathFinder


def make_path_finder(edges, node_types=None):
    """
    Helper: builds a MultiDiGraph from a list of (source, target, key, condition_type)
    tuples and wraps it into a PathFinder, exactly as PathFinder.__init__ expects.
    node_types lets a test mark specific nodes (not used by PathFinder itself today,
    but kept for parity with how the project's Parser would populate node data).
    """
    G = nx.MultiDiGraph()
    node_types = node_types or {}
    for source, target, key, condition_type in edges:
        G.add_node(source, type=node_types.get(source, "normal"))
        G.add_node(target, type=node_types.get(target, "normal"))
        G.add_edge(source, target, key=key, condition_type=condition_type)

    nodes_dict = dict(G.nodes(data=True))
    adj_dict = dict(G.adj)
    return PathFinder(nodes_dict, adj_dict, G), G


# ---------------------------------------------------------------------------
# __init__ / leaf node detection
# ---------------------------------------------------------------------------

class TestInit:
    """PathFinder.__init__ must correctly identify leaf nodes (out_degree == 0)."""

    def test_leaf_nodes_are_nodes_with_no_outgoing_edges(self):
        # Arrange: USER_ENTRY -> A -> B ; B has no outgoing edge, so it's the only leaf
        path_finder, _ = make_path_finder([
            ("USER_ENTRY", "A", 0, "DEFAULT"),
            ("A", "B", 0, "DEFAULT"),
        ])
        # Assert
        assert path_finder.leaf_nodes == ["B"]

    def test_multiple_leaf_nodes(self):
        # Arrange: USER_ENTRY branches into two dead ends, A and B
        path_finder, _ = make_path_finder([
            ("USER_ENTRY", "A", 0, "DEFAULT"),
            ("USER_ENTRY", "B", 0, "DEFAULT"),
        ])
        # Assert
        assert set(path_finder.leaf_nodes) == {"A", "B"}

    def test_a_graph_with_no_leaves(self):
        # Arrange: a pure cycle, every node always has an outgoing edge
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("B", "A", 0, "DEFAULT"),
        ])
        # Assert
        assert path_finder.leaf_nodes == []


# ---------------------------------------------------------------------------
# generate_paths - linear graph (fixes the pre-existing off-by-one test)
# ---------------------------------------------------------------------------

class TestGeneratePathsLinear:
    """
    generate_paths on USER_ENTRY -> Node_A -> Node_B (leaf).

    IMPORTANT: generate_paths() seeds the DFS with a synthetic "initial_step"
    (source=None, target=start_node) *before* exploring any edge (see line 25-30 of
    path_finder.py) -- it represents arriving at the start node itself, before any
    transition. So paths[0][0] is NOT the first real transition: paths[0][1] and
    paths[0][2] are. The original version of this test asserted on paths[0][0]/[1] and
    failed because of this; this is the corrected version, traced against the actual
    source instead of assumed.
    """

    @pytest.fixture
    def linear_graph(self):
        return make_path_finder([
            ("USER_ENTRY", "Node_A", 0, "DEFAULT"),
            ("Node_A", "Node_B", 0, "DEFAULT"),
        ])

    def test_finds_the_single_possible_path(self, linear_graph):
        path_finder, _ = linear_graph
        # Act
        paths = path_finder.generate_paths(start_node="USER_ENTRY")
        # Assert
        assert len(paths) == 1

    def test_the_synthetic_initial_step_has_no_source(self, linear_graph):
        path_finder, _ = linear_graph
        paths = path_finder.generate_paths(start_node="USER_ENTRY")
        initial_step = paths[0][0]
        assert initial_step["source"] is None
        assert initial_step["target"] == "USER_ENTRY"

    def test_the_two_real_transitions_come_after_the_initial_step(self, linear_graph):
        path_finder, _ = linear_graph
        paths = path_finder.generate_paths(start_node="USER_ENTRY")
        step1, step2 = paths[0][1], paths[0][2]
        assert step1["source"] == "USER_ENTRY"
        assert step1["target"] == "Node_A"
        assert step2["source"] == "Node_A"
        assert step2["target"] == "Node_B"


# ---------------------------------------------------------------------------
# generate_paths - branching
# ---------------------------------------------------------------------------

class TestGeneratePathsBranching:
    """A single DEFAULT branch into two separate dead ends must produce two paths."""

    def test_two_leaves_produce_two_distinct_paths(self):
        # Arrange: USER_ENTRY -> A (leaf), USER_ENTRY -> B (leaf)
        path_finder, _ = make_path_finder([
            ("USER_ENTRY", "A", 0, "DEFAULT"),
            ("USER_ENTRY", "B", 0, "DEFAULT"),
        ])
        # Act
        paths = path_finder.generate_paths(start_node="USER_ENTRY")
        # Assert
        assert len(paths) == 2
        targets_reached = {path[-1]["target"] for path in paths}
        assert targets_reached == {"A", "B"}


# ---------------------------------------------------------------------------
# generate_paths - parallel edges (MultiDiGraph edge coverage)
# ---------------------------------------------------------------------------

class TestGeneratePathsParallelEdges:
    """
    Two parallel edges between the SAME pair of nodes (e.g. a DEFAULT and a FALLBACK
    transition both going from A to B) must each get their own dedicated path: edge
    coverage is tracked per (source, target, key), not per node pair.
    """

    def test_both_parallel_edges_are_explored_separately(self):
        # Arrange: A -> B twice, with different condition_type/key
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("A", "B", 1, "FALLBACK"),
        ])
        # Act
        paths = path_finder.generate_paths(start_node="A")
        # Assert: two distinct paths, one per parallel edge
        assert len(paths) == 2
        condition_types = {path[1]["edge_data"]["condition_type"] for path in paths}
        assert condition_types == {"DEFAULT", "FALLBACK"}


# ---------------------------------------------------------------------------
# generate_paths - cycle detection (per-path `visited`) + escape route
# ---------------------------------------------------------------------------

class TestGeneratePathsLoop:
    """
    A -> B -> A (cycle) plus A -> C (leaf). When the DFS comes back to A while still
    inside the A-B branch, A is already in the per-path `visited` set: this must be
    flagged with is_loop=True and closed with an escape route to the leaf C, instead
    of recursing forever.
    """

    @pytest.fixture
    def cycle_graph(self):
        return make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("B", "A", 0, "DEFAULT"),
            ("A", "C", 0, "DEFAULT"),
        ])

    def test_two_paths_are_generated(self, cycle_graph):
        # Arrange/Act: one path goes A->B->A(loop, escapes to C), the other goes A->C directly
        path_finder, _ = cycle_graph
        paths = path_finder.generate_paths(start_node="A")
        # Assert
        assert len(paths) == 2

    def test_the_loop_branch_flags_is_loop_and_escapes_to_the_leaf(self, cycle_graph):
        path_finder, _ = cycle_graph
        paths = path_finder.generate_paths(start_node="A")

        # Find the path that actually goes through B
        loop_path = next(p for p in paths if any(step["target"] == "B" for step in p))

        # steps: [initial(A), A->B, B->A (loop), escape A->C]
        loop_step = next(step for step in loop_path if step.get("is_loop"))
        assert loop_step["source"] == "B"
        assert loop_step["target"] == "A"

        # The conversation must still end on the leaf C, not hang on the loop
        assert loop_path[-1]["target"] == "C"

    def test_the_direct_branch_reaches_the_leaf_without_looping(self, cycle_graph):
        path_finder, _ = cycle_graph
        paths = path_finder.generate_paths(start_node="A")
        direct_path = next(p for p in paths if not any(step["target"] == "B" for step in p))

        # steps: [initial(A), A->C]
        assert len(direct_path) == 2
        assert direct_path[1]["target"] == "C"
        assert "is_loop" not in direct_path[1]

    def test_every_edge_ends_up_globally_covered(self, cycle_graph):
        # Arrange/Act
        path_finder, _ = cycle_graph
        path_finder.generate_paths(start_node="A")
        # Assert: A->B, B->A and A->C were all visited exactly once each
        assert path_finder.global_visited_edges == {("A", "B", 0), ("B", "A", 0), ("A", "C", 0)}


# ---------------------------------------------------------------------------
# generate_paths - revisiting a node whose edges are already globally covered
# (the OTHER escape-route trigger, distinct from a same-path loop)
# ---------------------------------------------------------------------------

class TestGeneratePathsConvergingPaths:
    """
    A -> B -> X -> Y(leaf) and A -> C -> X (same X, reached via a different parent).

    The second time X is reached (via C), X is NOT in that branch's `visited` set
    (it's a brand new DFS branch), so this is NOT a cycle. But X's only outgoing edge
    (X->Y) was already added to global_visited_edges on the first visit (via B) --
    so `unvisited_edges` is empty even though self.adj[X] is not, which triggers the
    *other* escape-route branch (lines 116-122 of path_finder.py), without ever
    setting is_loop.
    """

    @pytest.fixture
    def diamond_graph(self):
        return make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("A", "C", 0, "DEFAULT"),
            ("B", "X", 0, "DEFAULT"),
            ("C", "X", 0, "DEFAULT"),
            ("X", "Y", 0, "DEFAULT"),
        ])

    def test_two_paths_are_generated(self, diamond_graph):
        path_finder, _ = diamond_graph
        paths = path_finder.generate_paths(start_node="A")
        assert len(paths) == 2

    def test_both_paths_reach_the_leaf_y_through_x(self, diamond_graph):
        path_finder, _ = diamond_graph
        paths = path_finder.generate_paths(start_node="A")
        for path in paths:
            assert path[-1]["target"] == "Y"

    def test_the_second_arrival_at_x_is_not_flagged_as_a_loop(self, diamond_graph):
        # Arrange/Act
        path_finder, _ = diamond_graph
        paths = path_finder.generate_paths(start_node="A")
        path_via_c = next(p for p in paths if any(step["target"] == "C" for step in p))
        # Assert: none of the steps on this path are flagged is_loop -- X->Y here comes
        # from the "already globally covered" escape branch, not from a cycle
        assert not any(step.get("is_loop") for step in path_via_c)

    def test_both_source_edges_into_x_are_covered_but_x_to_y_only_once_logically(self, diamond_graph):
        path_finder, _ = diamond_graph
        paths = path_finder.generate_paths(start_node="A")
        # Assert: every edge got a chance to be covered, including both (B,X) and (C,X)
        assert ("B", "X", 0) in path_finder.global_visited_edges
        assert ("C", "X", 0) in path_finder.global_visited_edges
        assert ("X", "Y", 0) in path_finder.global_visited_edges


# ---------------------------------------------------------------------------
# generate_paths - known limitation: not safe to call twice on the same instance
# ---------------------------------------------------------------------------

class TestGeneratePathsNotIdempotent:
    """
    self.all_test_paths and self.global_visited_edges are only initialized once, in
    __init__ -- generate_paths() never resets them. Calling generate_paths() a second
    time on the SAME PathFinder instance therefore starts from an already-"exhausted"
    state (every edge already globally visited), producing degenerate results instead
    of the same paths again.

    This is a characterization test, not a feature test: it documents a real
    constraint (always build a fresh PathFinder per generation run) rather than
    asserting it is correct behaviour. If this ever becomes a problem in practice
    (e.g. re-running generation after changing leaf_nodes), the fix is for
    generate_paths() to reset self.all_test_paths and self.global_visited_edges
    at the top of the method.
    """

    def test_calling_generate_paths_twice_leaks_state_into_all_test_paths(self):
        # Arrange: USER_ENTRY branches into two separate dead ends, A and B
        path_finder, _ = make_path_finder([
            ("USER_ENTRY", "A", 0, "DEFAULT"),
            ("USER_ENTRY", "B", 0, "DEFAULT"),
        ])
        # Act
        first_call = path_finder.generate_paths(start_node="USER_ENTRY")
        assert len(path_finder.all_test_paths) == 2

        second_call = path_finder.generate_paths(start_node="USER_ENTRY")

        # Assert: self.all_test_paths is only created in __init__ and never reset by
        # generate_paths(), so it keeps accumulating across calls on the same instance:
        # after the second call it holds 3 entries (the 2 original + 1 new one from the
        # second DFS run), not 2.
        assert len(path_finder.all_test_paths) == 3
        # The second call's OWN dfs run can no longer find any unvisited edge (both
        # USER_ENTRY->A and USER_ENTRY->B are already in global_visited_edges from the
        # first call), so it falls into the escape-route branch and synthesizes a
        # single new path to whichever leaf get_escape_path() picks first. In THIS
        # particular graph that synthesized path happens to be a content-duplicate of
        # one already in all_test_paths, so generate_paths()'s own dedup step still
        # returns 2 "unique" paths back to the caller -- but that's a coincidence of
        # this graph's shape (and of which leaf wins ties), not a guarantee: the
        # underlying state keeps leaking regardless. Always build a fresh PathFinder
        # per generation run instead of reusing one.
        assert len(second_call) == 2


# ---------------------------------------------------------------------------
# get_escape_path
# ---------------------------------------------------------------------------

class TestGetEscapePath:
    """get_escape_path: shortest route from a node to the nearest leaf, preferring
    already-visited edges so unvisited branches stay available for their own tests."""

    def test_no_leaf_nodes_returns_empty_list(self):
        # Arrange: a pure cycle has no leaves at all
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("B", "A", 0, "DEFAULT"),
        ])
        # Act / Assert
        assert path_finder.get_escape_path("A") == []

    def test_starting_already_at_the_leaf_returns_empty_list(self):
        # Arrange: B is itself the (only) leaf; asking for an escape route FROM B
        # means shortest_path_nodes == [B], length < 2
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
        ])
        # Act / Assert
        assert path_finder.get_escape_path("B") == []

    def test_simple_direct_route_to_the_only_leaf(self):
        # Arrange: A -> B -> C(leaf)
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("B", "C", 0, "DEFAULT"),
        ])
        # Act
        escape_steps = path_finder.get_escape_path("A")
        # Assert
        assert [ (s["source"], s["target"]) for s in escape_steps ] == [("A", "B"), ("B", "C")]

    def test_picks_the_nearest_of_several_leaves(self):
        # Arrange: A -> B (leaf, 1 hop) and A -> C -> D (leaf, 2 hops)
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("A", "C", 0, "DEFAULT"),
            ("C", "D", 0, "DEFAULT"),
        ])
        # Act
        escape_steps = path_finder.get_escape_path("A")
        # Assert: the 1-hop leaf B must be chosen over the 2-hop leaf D
        assert len(escape_steps) == 1
        assert escape_steps[0]["target"] == "B"

    def test_prefers_an_already_visited_edge_over_a_shorter_unvisited_one(self):
        # Arrange: A -> B (leaf, 1 hop, NOT yet visited) and A -> C -> D (leaf, 2 hops,
        # but BOTH edges already globally visited). The weight function makes an
        # already-visited edge cost 1 and an unvisited one cost 1000, so the "longer"
        # but already-covered route (cost 2) must still win over the shorter but
        # unvisited one (cost 1000).
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("A", "C", 0, "DEFAULT"),
            ("C", "D", 0, "DEFAULT"),
        ])
        path_finder.global_visited_edges = {("A", "C", 0), ("C", "D", 0)}
        # Act
        escape_steps = path_finder.get_escape_path("A")
        # Assert
        assert [s["target"] for s in escape_steps] == ["C", "D"]

    def test_picks_the_already_visited_parallel_edge_when_one_exists(self):
        # Arrange: two parallel A->B edges (key 0 unvisited, key 1 already visited).
        # The escape route should reuse the already-visited one (key 1).
        path_finder, _ = make_path_finder([
            ("A", "B", 0, "DEFAULT"),
            ("A", "B", 1, "FALLBACK"),
        ])
        path_finder.global_visited_edges = {("A", "B", 1)}
        # Act
        escape_steps = path_finder.get_escape_path("A")
        # Assert
        assert escape_steps[0]["edge_data"]["condition_type"] == "FALLBACK"
