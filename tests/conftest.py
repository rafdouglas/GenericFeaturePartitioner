"""Test configuration: QGIS mock injection and shared fixtures.

CRITICAL: The mock injection below MUST be bare module-level code,
NOT inside a fixture. Plugin files have top-level `from qgis.core import ...`
statements that execute during pytest collection, BEFORE any fixtures run.
"""

import sys
from unittest.mock import MagicMock

# Import our mock classes BEFORE any plugin code
from tests import qgis_mocks

# Build mock qgis.core module with all needed symbols
mock_qgis_core = MagicMock()

# Symbols imported by partitioner_utils.py (line 12)
mock_qgis_core.QgsGeometry = qgis_mocks.MockQgsGeometry
mock_qgis_core.QgsWkbTypes = qgis_mocks.MockQgsWkbTypes

# Symbols imported by partitioner_algorithm.py (lines 10-25)
mock_qgis_core.QgsFeature = qgis_mocks.MockQgsFeature
mock_qgis_core.QgsFeatureSink = qgis_mocks.MockQgsFeatureSink
mock_qgis_core.QgsField = qgis_mocks.MockQgsField
mock_qgis_core.QgsFields = qgis_mocks.MockQgsFields
mock_qgis_core.QgsProcessing = qgis_mocks.MockQgsProcessing
mock_qgis_core.QgsProcessingAlgorithm = qgis_mocks.MockQgsProcessingAlgorithm
mock_qgis_core.QgsProcessingException = qgis_mocks.MockQgsProcessingException
mock_qgis_core.QgsProcessingParameterNumber = qgis_mocks.MockQgsProcessingParameterNumber
mock_qgis_core.QgsProcessingParameterString = qgis_mocks.MockQgsProcessingParameterString
mock_qgis_core.QgsProcessingParameterVectorDestination = qgis_mocks.MockQgsProcessingParameterVectorDestination
mock_qgis_core.QgsProcessingParameterVectorLayer = qgis_mocks.MockQgsProcessingParameterVectorLayer
mock_qgis_core.QgsProcessingParameterDefinition = MagicMock()
mock_qgis_core.QgsSpatialIndex = qgis_mocks.MockQgsSpatialIndex
mock_qgis_core.QgsWkbTypes = qgis_mocks.MockQgsWkbTypes

# Symbols imported by partitioner_provider.py (line 1)
mock_qgis_core.QgsProcessingProvider = qgis_mocks.MockQgsProcessingProvider

# Symbols imported by __init__.py (lines 11, 19)
mock_qgis_core.QgsApplication = MagicMock()

# Build mock qgis.PyQt.QtCore (partitioner_algorithm.py:9)
mock_qtcore = MagicMock()
mock_qtcore.QMetaType = qgis_mocks.MockQMetaType

# Inject into sys.modules BEFORE any plugin imports
sys.modules["qgis"] = MagicMock()
sys.modules["qgis.core"] = mock_qgis_core
sys.modules["qgis.PyQt"] = MagicMock()
sys.modules["qgis.PyQt.QtCore"] = mock_qtcore

# NOW it is safe to import plugin modules and define fixtures
import pytest
from shapely.geometry import LineString, LinearRing, Polygon, box


@pytest.fixture
def simple_square():
    """A simple 10x10 square polygon."""
    return box(0, 0, 10, 10)


@pytest.fixture
def square_with_hole():
    """A 10x10 square with a 2x2 hole in the center."""
    exterior = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    hole = [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]
    return Polygon(exterior, [hole])


@pytest.fixture
def l_shaped_polygon():
    """An L-shaped non-convex polygon."""
    coords = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10), (0, 0)]
    return Polygon(coords)


@pytest.fixture
def horizontal_bisector():
    """A horizontal line at y=5 spanning wider than the 10x10 square."""
    return LineString([(-1, 5), (11, 5)])


@pytest.fixture
def cross_lines():
    """Two perpendicular lines cutting a 10x10 square into 4 quadrants."""
    return [
        LineString([(-1, 5), (11, 5)]),  # horizontal
        LineString([(5, -1), (5, 11)]),   # vertical
    ]
