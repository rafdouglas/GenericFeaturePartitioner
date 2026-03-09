"""Unit tests for QGIS wrapper functions in partitioner_utils.py."""

import pytest
from shapely.geometry import box

from generic_feature_partitioner.partitioner_utils import (
    HAS_SHAPELY,
    drop_zm,
    qgs_to_shapely,
    shapely_to_qgs,
)
from tests.qgis_mocks import MockQgsGeometry


class TestDropZm:
    def test_none_input(self):
        result = drop_zm(None)
        assert result is None

    def test_empty_geometry(self):
        geom = MockQgsGeometry()  # _wkb is None -> isEmpty() returns True
        result = drop_zm(geom)
        assert result is geom  # same object returned

    def test_2d_geometry_unchanged(self):
        geom = MockQgsGeometry.from_shapely(box(0, 0, 10, 10))
        geom._wkb_type = 3  # Polygon, no Z/M flags
        result = drop_zm(geom)
        assert result is geom  # identity check - same object

    def test_zm_geometry(self):
        geom = MockQgsGeometry.from_shapely(box(0, 0, 10, 10))
        geom._wkb_type = 0x3000 | 3  # Z + M flags set
        result = drop_zm(geom)
        assert result is not geom  # new object created
        assert result._drop_z_called
        assert result._drop_m_called


class TestConversions:
    def test_qgs_to_shapely_polygon(self):
        shapely_poly = box(0, 0, 10, 10)
        qgs_geom = MockQgsGeometry.from_shapely(shapely_poly)
        result = qgs_to_shapely(qgs_geom)
        assert result.equals(shapely_poly)

    def test_shapely_to_qgs_polygon(self):
        shapely_poly = box(0, 0, 10, 10)
        qgs_geom = shapely_to_qgs(shapely_poly)
        assert isinstance(qgs_geom, MockQgsGeometry)
        assert not qgs_geom.isEmpty()

    def test_conversion_roundtrip(self):
        original = box(5, 5, 15, 15)
        qgs_geom = shapely_to_qgs(original)
        roundtripped = qgs_to_shapely(qgs_geom)
        assert roundtripped.equals(original)


class TestHasShapely:
    def test_has_shapely_true(self):
        assert HAS_SHAPELY is True
