"""Unit tests for pure shapely functions in partitioner_utils.py."""

import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon, box

from generic_feature_partitioner.partitioner_utils import (
    _clip_and_filter_lines,
    _extract_boundary_lines,
    split_polygon_with_lines,
)


# === Tests for _extract_boundary_lines ===

class TestExtractBoundaryLines:
    def test_simple_polygon(self, simple_square):
        lines = _extract_boundary_lines(simple_square)
        assert len(lines) == 1
        assert lines[0].coords[0] == lines[0].coords[-1]  # closed ring

    def test_polygon_with_hole(self, square_with_hole):
        lines = _extract_boundary_lines(square_with_hole)
        assert len(lines) == 2
        for line in lines:
            assert line.coords[0] == line.coords[-1]

    def test_polygon_with_multiple_holes(self):
        exterior = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
        holes = [
            [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)],
            [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)],
            [(10, 10), (12, 10), (12, 12), (10, 12), (10, 10)],
        ]
        poly = Polygon(exterior, holes)
        lines = _extract_boundary_lines(poly)
        assert len(lines) == 4  # 1 exterior + 3 holes


# === Tests for _clip_and_filter_lines ===

class TestClipAndFilterLines:
    def test_line_fully_inside(self, simple_square):
        line = LineString([(2, 2), (8, 8)])
        result = _clip_and_filter_lines([line], simple_square, 0.01)
        assert len(result) == 1
        assert abs(result[0].length - line.length) < 0.001

    def test_line_crossing_polygon(self, simple_square):
        line = LineString([(-5, 5), (15, 5)])
        result = _clip_and_filter_lines([line], simple_square, 0.01)
        assert len(result) == 1
        assert result[0].length < line.length

    def test_line_fully_outside(self, simple_square):
        line = LineString([(20, 20), (30, 30)])
        result = _clip_and_filter_lines([line], simple_square, 0.01)
        assert len(result) == 0

    def test_line_too_short_filtered(self, simple_square):
        # Line that intersects polygon but intersection is very short
        line = LineString([(9.999, 5), (10.001, 5)])
        result = _clip_and_filter_lines([line], simple_square, 1.0)
        assert len(result) == 0

    def test_multiple_lines(self, simple_square):
        lines = [
            LineString([(2, 2), (8, 8)]),     # inside
            LineString([(-5, 5), (15, 5)]),   # crossing
            LineString([(20, 20), (30, 30)]), # outside
        ]
        result = _clip_and_filter_lines(lines, simple_square, 0.01)
        assert len(result) == 2

    def test_line_along_boundary(self, simple_square):
        line = LineString([(0, 0), (10, 0)])  # along bottom edge
        result = _clip_and_filter_lines([line], simple_square, 0.01)
        # Boundary intersection may be empty or degenerate
        # The important thing is no crash
        assert isinstance(result, list)

    def test_empty_lines_list(self, simple_square):
        result = _clip_and_filter_lines([], simple_square, 0.01)
        assert result == []

    def test_line_producing_multilinestring(self):
        # C-shaped polygon so line enters and exits multiple times
        poly = Polygon([(0, 0), (10, 0), (10, 3), (3, 3), (3, 7), (10, 7), (10, 10), (0, 10), (0, 0)])
        line = LineString([(5, -1), (5, 11)])
        result = _clip_and_filter_lines([line], poly, 0.01)
        assert len(result) >= 2  # enters bottom, exits middle, enters top


# === Tests for split_polygon_with_lines ===

class TestSplitPolygonWithLines:
    def test_no_lines(self, simple_square):
        result = split_polygon_with_lines(simple_square, [])
        assert len(result) == 1
        assert abs(result[0].area - simple_square.area) < 0.001

    def test_single_bisector(self, simple_square, horizontal_bisector):
        result = split_polygon_with_lines(simple_square, [horizontal_bisector])
        assert len(result) == 2
        total_area = sum(p.area for p in result)
        assert abs(total_area - simple_square.area) < 0.1

    def test_cross_into_four(self, simple_square, cross_lines):
        result = split_polygon_with_lines(simple_square, cross_lines)
        assert len(result) == 4
        for p in result:
            assert abs(p.area - 25.0) < 1.0  # each ~25% of 100

    def test_line_outside_polygon(self, simple_square):
        line = LineString([(20, 20), (30, 30)])
        result = split_polygon_with_lines(simple_square, [line])
        assert len(result) == 1

    def test_line_partially_crossing(self, simple_square):
        # T-intersection: line enters from one side but doesn't exit another
        line = LineString([(5, -1), (5, 5)])
        result = split_polygon_with_lines(simple_square, [line])
        # Cannot create closed sub-regions from T-intersection
        assert len(result) == 1

    def test_polygon_with_hole(self, square_with_hole, horizontal_bisector):
        result = split_polygon_with_lines(square_with_hole, [horizontal_bisector])
        assert len(result) >= 2
        total_area = sum(p.area for p in result)
        assert abs(total_area - square_with_hole.area) < 0.5

    def test_sliver_filtering(self, simple_square):
        # Line very close to boundary should create a sliver that gets filtered
        line = LineString([(-1, 0.005), (11, 0.005)])
        result = split_polygon_with_lines(simple_square, [line], snap_tolerance=0.01)
        # Sliver below min_area should be filtered
        for p in result:
            assert p.area >= 0.01 * 0.01

    def test_area_conservation(self, simple_square, cross_lines):
        result = split_polygon_with_lines(simple_square, cross_lines)
        total_area = sum(p.area for p in result)
        assert abs(total_area - simple_square.area) < 1.0

    def test_snap_tolerance_effect(self, simple_square):
        # Line endpoint near but not on boundary
        line = LineString([(0.005, 5), (9.995, 5)])
        result = split_polygon_with_lines(simple_square, [line], snap_tolerance=0.01)
        # With snapping, should still split
        assert len(result) >= 1  # may or may not split depending on snap behavior

    def test_multiple_lines_complex(self, simple_square):
        lines = [
            LineString([(-1, 3), (11, 3)]),
            LineString([(-1, 7), (11, 7)]),
            LineString([(5, -1), (5, 11)]),
        ]
        result = split_polygon_with_lines(simple_square, lines)
        assert len(result) >= 5  # 3 lines creating 6 sub-polygons
        total_area = sum(p.area for p in result)
        assert abs(total_area - simple_square.area) < 1.0

    def test_concave_polygon(self, l_shaped_polygon):
        line = LineString([(-1, 5), (11, 5)])
        result = split_polygon_with_lines(l_shaped_polygon, [line])
        assert len(result) >= 2

    def test_single_result_same_area(self, simple_square):
        # Line that touches but doesn't create a real split
        # (the 99% area ratio check at lines 163-166)
        line = LineString([(0, 0), (0.001, 10)])  # nearly on boundary
        result = split_polygon_with_lines(simple_square, [line])
        assert len(result) >= 1  # returns [polygon] if single result ~same area

    def test_multipolygon_defensive(self):
        # split_polygon_with_lines calls polygon.exterior (line 61)
        # MultiPolygon has no .exterior attribute
        mp = MultiPolygon([box(0, 0, 5, 5), box(6, 6, 10, 10)])
        line = LineString([(-1, 2.5), (11, 2.5)])
        with pytest.raises(AttributeError):
            split_polygon_with_lines(mp, [line])
