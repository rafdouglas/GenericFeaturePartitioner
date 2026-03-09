"""Mock classes for QGIS types used in testing without QGIS installed."""

from unittest.mock import MagicMock
from shapely import wkb as shapely_wkb


class MockQgsWkbTypes:
    """Mock for qgis.core.QgsWkbTypes."""
    MultiPolygon = 6

    @staticmethod
    def hasZ(wkb_type):
        return bool(wkb_type & 0x1000)

    @staticmethod
    def hasM(wkb_type):
        return bool(wkb_type & 0x2000)


class MockQgsGeometry:
    """Mock for qgis.core.QgsGeometry wrapping shapely geometry via WKB."""

    def __init__(self, other=None):
        self._wkb = None
        self._wkb_type = 0
        self._drop_z_called = False
        self._drop_m_called = False
        self._convert_multi_called = False
        if isinstance(other, MockQgsGeometry):
            self._wkb = other._wkb
            self._wkb_type = other._wkb_type
        elif other is not None:
            # Treat as a clone-like object (from constGet().clone())
            if hasattr(other, '_wkb'):
                self._wkb = other._wkb
                self._wkb_type = getattr(other, '_wkb_type', 0)

    @classmethod
    def from_shapely(cls, shapely_geom):
        """Helper to create MockQgsGeometry from a shapely geometry."""
        obj = cls()
        obj._wkb = shapely_geom.wkb
        return obj

    def asWkb(self):
        return self._wkb if self._wkb else b''

    def fromWkb(self, data):
        if isinstance(data, (bytes, bytearray)):
            self._wkb = bytes(data)
        else:
            self._wkb = bytes(data)

    def isEmpty(self):
        return self._wkb is None or len(self._wkb) == 0

    def wkbType(self):
        return self._wkb_type

    def constGet(self):
        parent = self
        class CloneWrapper:
            def clone(self_inner):
                clone = _ClonedGeom()
                clone._wkb = parent._wkb
                clone._wkb_type = parent._wkb_type
                return clone
        return CloneWrapper()

    def get(self):
        parent = self
        class MutableWrapper:
            def dropZValue(self_inner):
                parent._drop_z_called = True
            def dropMValue(self_inner):
                parent._drop_m_called = True
        return MutableWrapper()

    def intersects(self, other):
        if self._wkb and other._wkb:
            s1 = shapely_wkb.loads(self._wkb)
            s2 = shapely_wkb.loads(other._wkb)
            return s1.intersects(s2)
        return False

    def boundingBox(self):
        if self._wkb:
            geom = shapely_wkb.loads(self._wkb)
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            return MockQgsRectangle(*bounds)
        return MockQgsRectangle(0, 0, 0, 0)

    def convertToMultiType(self):
        self._convert_multi_called = True


class _ClonedGeom:
    """Internal helper for constGet().clone() result."""
    def __init__(self):
        self._wkb = None
        self._wkb_type = 0


class MockQgsRectangle:
    """Mock for QgsRectangle (bounding box)."""
    def __init__(self, xmin, ymin, xmax, ymax):
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax

    def xMinimum(self):
        return self.xmin
    def yMinimum(self):
        return self.ymin
    def xMaximum(self):
        return self.xmax
    def yMaximum(self):
        return self.ymax

    def intersects(self, other):
        return not (self.xmax < other.xmin or other.xmax < self.xmin or
                    self.ymax < other.ymin or other.ymax < self.ymin)


class MockQgsFeature:
    """Mock for qgis.core.QgsFeature."""

    def __init__(self, fields_or_other=None):
        self._fid = 0
        self._geometry = MockQgsGeometry()
        self._attributes = []
        self._attr_map = {}
        self._fields = None
        if isinstance(fields_or_other, MockQgsFeature):
            self._fid = fields_or_other._fid
            self._geometry = MockQgsGeometry(fields_or_other._geometry)
            self._attributes = list(fields_or_other._attributes)
            self._attr_map = dict(fields_or_other._attr_map)
            self._fields = fields_or_other._fields
        elif isinstance(fields_or_other, MockQgsFields):
            self._fields = fields_or_other

    def id(self):
        return self._fid

    def setId(self, fid):
        self._fid = fid

    def geometry(self):
        return self._geometry

    def setGeometry(self, geom):
        self._geometry = geom

    def attributes(self):
        return list(self._attributes)

    def setAttributes(self, attrs):
        self._attributes = list(attrs)

    def __getitem__(self, field_name):
        return self._attr_map.get(field_name)


class MockQgsField:
    """Mock for qgis.core.QgsField."""
    def __init__(self, name="", type_val=None, *args, **kwargs):
        self._name = name
        self._type = type_val

    def name(self):
        return self._name


class MockQgsFields:
    """Mock for qgis.core.QgsFields."""
    def __init__(self, other=None):
        if isinstance(other, MockQgsFields):
            self._fields = list(other._fields)
        else:
            self._fields = []

    def append(self, field):
        self._fields.append(field)

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)


class MockQgsSpatialIndex:
    """Mock for qgis.core.QgsSpatialIndex - simple linear scan."""
    def __init__(self):
        self._entries = []  # list of (fid, bbox)

    def addFeature(self, feat):
        bbox = feat.geometry().boundingBox()
        self._entries.append((feat.id(), bbox))
        return True

    def intersects(self, rect):
        result = []
        for fid, bbox in self._entries:
            if bbox.intersects(rect):
                result.append(fid)
        return result


class MockQgsFeatureSink:
    """Mock for qgis.core.QgsFeatureSink."""
    FastInsert = 1

    def __init__(self):
        self.features = []

    def addFeature(self, feat, flags=None):
        self.features.append(feat)
        return True


class MockQgsProcessingAlgorithm:
    """Mock base class for qgis.core.QgsProcessingAlgorithm."""

    def __init__(self):
        self._parameters = []

    def addParameter(self, param):
        self._parameters.append(param)

    def parameterAsVectorLayer(self, params, name, context):
        return params[name]

    def parameterAsString(self, params, name, context):
        return params[name]

    def parameterAsDouble(self, params, name, context):
        return float(params[name])

    def parameterAsSink(self, params, name, context, fields, geom_type, crs):
        sink = MockQgsFeatureSink()
        return (sink, "output_id")

    def invalidSinkError(self, params, name):
        return f"Invalid sink: {name}"


class MockQgsProcessingException(Exception):
    """Mock for qgis.core.QgsProcessingException."""
    pass


class MockQgsProcessingProvider:
    """Mock base class for qgis.core.QgsProcessingProvider."""
    def __init__(self):
        self._algorithms = []

    def addAlgorithm(self, alg):
        self._algorithms.append(alg)


class MockQgsProcessing:
    """Mock for qgis.core.QgsProcessing."""
    TypeVectorPolygon = 3
    TypeVectorLine = 1


class MockQgsProcessingParameterNumber:
    """Mock for qgis.core.QgsProcessingParameterNumber."""
    Double = 1
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MockQgsProcessingParameterString:
    """Mock for qgis.core.QgsProcessingParameterString."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MockQgsProcessingParameterVectorDestination:
    """Mock for qgis.core.QgsProcessingParameterVectorDestination."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MockQgsProcessingParameterVectorLayer:
    """Mock for qgis.core.QgsProcessingParameterVectorLayer."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MockQMetaType:
    """Mock for qgis.PyQt.QtCore.QMetaType."""
    class Type:
        LongLong = 4
        Int = 2


class MockFeedback:
    """Mock for QgsProcessingFeedback."""
    def __init__(self):
        self.messages = []
        self.errors = []
        self.progress_values = []
        self._canceled = False

    def pushInfo(self, msg):
        self.messages.append(msg)

    def reportError(self, msg):
        self.errors.append(msg)

    def setProgress(self, val):
        self.progress_values.append(val)

    def isCanceled(self):
        return self._canceled


class MockVectorLayer:
    """Mock for qgis.core.QgsVectorLayer."""
    def __init__(self, features=None, fields=None):
        self._features = features or []
        self._fields = fields or MockQgsFields()
        self._crs = MagicMock()

    def getFeatures(self):
        return iter(self._features)

    def fields(self):
        return self._fields

    def crs(self):
        return self._crs
