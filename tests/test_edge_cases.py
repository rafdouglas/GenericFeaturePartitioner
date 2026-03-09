"""Edge case tests for split_polygon_with_lines - pure shapely, no QGIS."""

import pytest
from shapely.geometry import LineString, Polygon, box

from generic_feature_partitioner.partitioner_utils import split_polygon_with_lines


class TestEdgeCases:
    def test_degenerate_polygon_zero_area(self):
        """Polygon collapsed to a line (zero area)."""
        poly = Polygon([(0, 0), (10, 0), (10, 0), (0, 0)])
        line = LineString([(-1, 0), (11, 0)])
        result = split_polygon_with_lines(poly, [line])
        assert isinstance(result, list)

    def test_self_intersecting_polygon(self):
        """Self-intersecting (bowtie) polygon - graceful handling."""
        poly = Polygon([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])
        line = LineString([(-1, 5), (11, 5)])
        result = split_polygon_with_lines(poly, [line])
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_very_small_polygon(self):
        """Polygon smaller than snap_tolerance squared."""
        poly = box(0, 0, 0.001, 0.001)
        line = LineString([(-1, 0.0005), (1, 0.0005)])
        result = split_polygon_with_lines(poly, [line], snap_tolerance=0.01)
        assert isinstance(result, list)

    def test_very_large_snap_tolerance(self):
        """Snap tolerance larger than polygon - no crash."""
        poly = box(0, 0, 1, 1)
        line = LineString([(-1, 0.5), (2, 0.5)])
        result = split_polygon_with_lines(poly, [line], snap_tolerance=100.0)
        assert isinstance(result, list)

    def test_zero_snap_tolerance(self):
        """snap_tolerance=0 - no division by zero or infinite loop."""
        poly = box(0, 0, 10, 10)
        line = LineString([(-1, 5), (11, 5)])
        result = split_polygon_with_lines(poly, [line], snap_tolerance=0)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_coincident_lines(self):
        """Multiple identical lines should not duplicate results."""
        poly = box(0, 0, 10, 10)
        line = LineString([(-1, 5), (11, 5)])
        result = split_polygon_with_lines(poly, [line, line, line])
        assert len(result) == 2  # same as single line split

    def test_line_touching_vertex(self):
        """Line endpoint exactly on polygon vertex."""
        poly = box(0, 0, 10, 10)
        line = LineString([(0, 0), (10, 10)])  # diagonal through vertices
        result = split_polygon_with_lines(poly, [line])
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_many_lines(self):
        """50+ lines splitting a polygon - performance check."""
        poly = box(0, 0, 100, 100)
        lines = [LineString([(-1, y), (101, y)]) for y in range(2, 100, 2)]
        assert len(lines) >= 49
        result = split_polygon_with_lines(poly, lines, snap_tolerance=0.1)
        assert len(result) >= 2
        total_area = sum(p.area for p in result)
        assert abs(total_area - poly.area) < 10.0

    def test_polygon_with_many_holes(self):
        """Polygon with 10+ holes split by a line."""
        exterior = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        holes = []
        for i in range(12):
            x = 5 + (i % 4) * 22
            y = 5 + (i // 4) * 30
            holes.append([(x, y), (x+5, y), (x+5, y+5), (x, y+5), (x, y)])
        poly = Polygon(exterior, holes)
        assert poly.is_valid
        line = LineString([(-1, 50), (101, 50)])
        result = split_polygon_with_lines(poly, [line])
        assert len(result) >= 2
        # Holes should be preserved
        total_area = sum(p.area for p in result)
        assert abs(total_area - poly.area) < 5.0

    def test_nearly_coincident_boundary(self):
        """Line nearly coincident with polygon boundary (within snap_tolerance)."""
        poly = box(0, 0, 10, 10)
        # Line very close to bottom edge
        line = LineString([(-1, 0.005), (11, 0.005)])
        result = split_polygon_with_lines(poly, [line], snap_tolerance=0.01)
        assert isinstance(result, list)
        # No sliver artifacts
        for p in result:
            assert p.area >= 0.01 * 0.01
