"""Unit tests for SplitPolygonsAlgorithm in partitioner_algorithm.py."""

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import box

from generic_feature_partitioner.partitioner_algorithm import SplitPolygonsAlgorithm
from tests.qgis_mocks import (
    MockFeedback,
    MockQgsFeature,
    MockQgsFeatureSink,
    MockQgsFields,
    MockQgsGeometry,
    MockQgsProcessingException,
    MockVectorLayer,
)


def make_feature(fid, shapely_geom, attr_map=None, attributes=None):
    """Create a MockQgsFeature with geometry and attributes."""
    feat = MockQgsFeature()
    feat._fid = fid
    feat._geometry = MockQgsGeometry.from_shapely(shapely_geom)
    feat._attr_map = attr_map or {}
    feat._attributes = attributes or []
    return feat


def run_algorithm(
    poly_features,
    line_features,
    poly_filter_field="",
    poly_filter_value="",
    line_filter_field="",
    line_filter_value="",
    snap_tolerance=0.01,
    split_return=None,
    has_shapely=True,
    split_side_effect=None,
):
    """Run SplitPolygonsAlgorithm with mocked dependencies.

    Args:
        poly_features: list of MockQgsFeature for polygon layer
        line_features: list of MockQgsFeature for line layer
        poly_filter_field/value: polygon filter settings
        line_filter_field/value: line filter settings
        snap_tolerance: snap tolerance value
        split_return: return value for split_polygon_with_lines mock
                     (default: returns [input_polygon] unchanged)
        has_shapely: whether HAS_SHAPELY is True
        split_side_effect: side effect for split_polygon_with_lines mock

    Returns:
        (sink_features, feedback, result_dict)
    """
    # 1. Instantiate algorithm and register parameters
    algorithm = SplitPolygonsAlgorithm()
    algorithm.initAlgorithm({})

    # 2. Build mock layers
    poly_layer = MockVectorLayer(features=poly_features)
    line_layer = MockVectorLayer(features=line_features)

    # 3. Build parameters dict
    parameters = {
        "INPUT_POLYGONS": poly_layer,
        "INPUT_LINES": line_layer,
        "POLYGON_FILTER_FIELD": poly_filter_field,
        "POLYGON_FILTER_VALUE": poly_filter_value,
        "LINE_FILTER_FIELD": line_filter_field,
        "LINE_FILTER_VALUE": line_filter_value,
        "SNAP_TOLERANCE": snap_tolerance,
        "OUTPUT": "output",
    }

    # 4. Create feedback and context
    feedback = MockFeedback()
    context = MagicMock()

    # 5. Set up the sink
    sink = MockQgsFeatureSink()

    # 6. Patch all utility functions at their import location in partitioner_algorithm
    module_path = "generic_feature_partitioner.partitioner_algorithm"

    with contextlib.ExitStack() as stack:
        # Patch HAS_SHAPELY
        stack.enter_context(patch(f"{module_path}.HAS_SHAPELY", has_shapely))

        # Patch drop_zm to return geometry unchanged
        stack.enter_context(patch(
            f"{module_path}.drop_zm",
            side_effect=lambda geom: geom,
        ))

        # Patch qgs_to_shapely to convert MockQgsGeometry WKB to shapely
        from shapely import wkb as shapely_wkb
        stack.enter_context(patch(
            f"{module_path}.qgs_to_shapely",
            side_effect=lambda geom: shapely_wkb.loads(geom.asWkb()),
        ))

        # Patch shapely_to_qgs to wrap shapely back to MockQgsGeometry
        stack.enter_context(patch(
            f"{module_path}.shapely_to_qgs",
            side_effect=lambda geom: MockQgsGeometry.from_shapely(geom),
        ))

        # Patch split_polygon_with_lines
        split_mock = MagicMock()
        if split_side_effect:
            split_mock.side_effect = split_side_effect
        elif split_return is not None:
            split_mock.return_value = split_return
        else:
            # Default: return [input_polygon] (no split)
            split_mock.side_effect = lambda poly, lines, snap_tolerance: [poly]
        stack.enter_context(patch(
            f"{module_path}.split_polygon_with_lines",
            split_mock,
        ))

        # Patch parameterAsSink on the instance to return our controlled sink
        stack.enter_context(patch.object(
            algorithm, "parameterAsSink",
            return_value=(sink, "dest_id"),
        ))

        result = algorithm.processAlgorithm(parameters, context, feedback)

    return sink.features, feedback, result, split_mock


class TestAlgorithmMetadata:
    def test_metadata_and_init(self):
        alg = SplitPolygonsAlgorithm()
        assert alg.name() == "splitpolygonswithlines"
        assert alg.displayName() == "Split Polygons with Partition Lines"
        assert alg.group() == "Vector geometry"
        assert alg.groupId() == "vectorgeometry"

        new_instance = alg.createInstance()
        assert isinstance(new_instance, SplitPolygonsAlgorithm)
        assert new_instance is not alg

        alg.initAlgorithm({})
        assert len(alg._parameters) == 8


class TestProcessAlgorithm:
    def test_no_intersecting_lines(self):
        """1 polygon, 0 lines -> polygon copied as-is with SUB_ID=0."""
        poly = make_feature(1, box(0, 0, 10, 10), attributes=["val1"])
        features, feedback, result, split_mock = run_algorithm(
            poly_features=[poly],
            line_features=[],
        )
        assert len(features) == 1
        assert features[0].attributes()[-2:] == [1, 0]  # PARENT_FID=1, SUB_ID=0
        split_mock.assert_not_called()

    def test_simple_split(self):
        """1 polygon + 1 intersecting line -> 2 output features."""
        square = box(0, 0, 10, 10)
        poly = make_feature(1, square, attributes=["val1"])

        from shapely.geometry import LineString
        line_geom = LineString([(-1, 5), (11, 5)])
        line = make_feature(10, line_geom, attributes=["lval"])

        left_half = box(0, 0, 10, 5)
        right_half = box(0, 5, 10, 10)

        features, feedback, result, split_mock = run_algorithm(
            poly_features=[poly],
            line_features=[line],
            split_return=[left_half, right_half],
        )
        assert len(features) == 2
        assert features[0].attributes()[-2:] == [1, 1]  # PARENT_FID=1, SUB_ID=1
        assert features[1].attributes()[-2:] == [1, 2]  # PARENT_FID=1, SUB_ID=2
        split_mock.assert_called_once()

    def test_filter_fields(self):
        """Filter both polygon and line features by field values."""
        poly_a1 = make_feature(1, box(0, 0, 10, 10), attr_map={"TYPE": "A"}, attributes=["A"])
        poly_b = make_feature(2, box(20, 0, 30, 10), attr_map={"TYPE": "B"}, attributes=["B"])
        poly_a2 = make_feature(3, box(0, 20, 10, 30), attr_map={"TYPE": "A"}, attributes=["A"])

        from shapely.geometry import LineString
        line_x1 = make_feature(10, LineString([(-1, 5), (11, 5)]), attr_map={"KIND": "X"}, attributes=["X"])
        line_y = make_feature(11, LineString([(25, -1), (25, 11)]), attr_map={"KIND": "Y"}, attributes=["Y"])
        line_x2 = make_feature(12, LineString([(-1, 25), (11, 25)]), attr_map={"KIND": "X"}, attributes=["X"])

        features, feedback, result, _ = run_algorithm(
            poly_features=[poly_a1, poly_b, poly_a2],
            line_features=[line_x1, line_y, line_x2],
            poly_filter_field="TYPE",
            poly_filter_value="A",
            line_filter_field="KIND",
            line_filter_value="X",
        )
        # Only 2 polygons processed (TYPE=A), B is skipped
        # Should have output features for the 2 filtered polygons
        assert len(features) == 2
        # Check that "Indexed 2 line features" appears in feedback
        indexed_msg = [m for m in feedback.messages if "Indexed 2" in m]
        assert len(indexed_msg) == 1

    def test_empty_polygon_skipped(self):
        """Empty geometry polygon should be skipped with error."""
        poly = MockQgsFeature()
        poly._fid = 1
        poly._geometry = MockQgsGeometry()  # empty
        poly._attributes = ["val"]

        features, feedback, result, _ = run_algorithm(
            poly_features=[poly],
            line_features=[],
        )
        assert len(features) == 0
        assert any("empty or null geometry" in e for e in feedback.errors)

    def test_no_shapely_raises(self):
        """HAS_SHAPELY=False should raise QgsProcessingException."""
        poly = make_feature(1, box(0, 0, 10, 10))
        with pytest.raises(MockQgsProcessingException, match="shapely"):
            run_algorithm(
                poly_features=[poly],
                line_features=[],
                has_shapely=False,
            )

    def test_split_error_fallback(self):
        """Split error -> copy original polygon with SUB_ID=0."""
        poly = make_feature(1, box(0, 0, 10, 10), attributes=["val1"])

        from shapely.geometry import LineString
        line = make_feature(10, LineString([(-1, 5), (11, 5)]), attributes=["lval"])

        features, feedback, result, _ = run_algorithm(
            poly_features=[poly],
            line_features=[line],
            split_side_effect=RuntimeError("test error"),
        )
        assert len(features) == 1
        assert features[0].attributes()[-2:] == [1, 0]  # SUB_ID=0 (fallback)
        assert any("split failed" in e for e in feedback.errors)
