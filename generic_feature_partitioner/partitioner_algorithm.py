"""
QGIS Processing algorithm: Split Polygons with Partition Lines.

Splits polygon features using intersecting line features via a
topology/polygonize approach. Each polygon is split independently,
preserving original attributes and adding PARENT_FID and SUB_ID fields.
"""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsWkbTypes,
)

from .partitioner_utils import (
    HAS_SHAPELY,
    drop_zm,
    qgs_to_shapely,
    shapely_to_qgs,
    split_polygon_with_lines,
)


class SplitPolygonsAlgorithm(QgsProcessingAlgorithm):

    INPUT_POLYGONS = "INPUT_POLYGONS"
    INPUT_LINES = "INPUT_LINES"
    POLYGON_FILTER_FIELD = "POLYGON_FILTER_FIELD"
    POLYGON_FILTER_VALUE = "POLYGON_FILTER_VALUE"
    LINE_FILTER_FIELD = "LINE_FILTER_FIELD"
    LINE_FILTER_VALUE = "LINE_FILTER_VALUE"
    SNAP_TOLERANCE = "SNAP_TOLERANCE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "splitpolygonswithlines"

    def displayName(self):
        return "Split Polygons with Partition Lines"

    def group(self):
        return "Vector geometry"

    def groupId(self):
        return "vectorgeometry"

    def shortHelpString(self):
        return (
            "Splits polygon features using intersecting line features "
            "via a topology/polygonize approach.\n\n"
            "For each filtered polygon, the algorithm finds intersecting "
            "filtered lines, builds a planar topology from the polygon "
            "boundary plus clipped lines, and polygonizes to create "
            "sub-polygons.\n\n"
            "Output features retain all original polygon attributes plus:\n"
            "- PARENT_FID: original feature ID for traceability\n"
            "- SUB_ID: 0 for unsplit polygons, 1..N for sub-polygons"
        )

    def createInstance(self):
        return SplitPolygonsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POLYGONS,
                "Input polygon layer (e.g. AREA)",
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_LINES,
                "Input line layer (e.g. LINE)",
                [QgsProcessing.TypeVectorLine],
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.POLYGON_FILTER_FIELD,
                "Polygon filter field",
                defaultValue="NOME_CLAS",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.POLYGON_FILTER_VALUE,
                "Polygon filter value",
                defaultValue="EDIFICATO",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.LINE_FILTER_FIELD,
                "Line filter field",
                defaultValue="NOME_CLAS",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.LINE_FILTER_VALUE,
                "Line filter value",
                defaultValue="EDIFICATO",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SNAP_TOLERANCE,
                "Snap tolerance (map units)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.01,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                "Output layer",
                type=QgsProcessing.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        if not HAS_SHAPELY:
            raise QgsProcessingException(
                "shapely is required but not available. "
                "Install it with: pip install shapely"
            )

        # Resolve parameters
        poly_layer = self.parameterAsVectorLayer(
            parameters, self.INPUT_POLYGONS, context
        )
        line_layer = self.parameterAsVectorLayer(
            parameters, self.INPUT_LINES, context
        )
        poly_filter_field = self.parameterAsString(
            parameters, self.POLYGON_FILTER_FIELD, context
        )
        poly_filter_value = self.parameterAsString(
            parameters, self.POLYGON_FILTER_VALUE, context
        )
        line_filter_field = self.parameterAsString(
            parameters, self.LINE_FILTER_FIELD, context
        )
        line_filter_value = self.parameterAsString(
            parameters, self.LINE_FILTER_VALUE, context
        )
        snap_tolerance = self.parameterAsDouble(
            parameters, self.SNAP_TOLERANCE, context
        )

        # Build output fields: original polygon fields + PARENT_FID + SUB_ID
        output_fields = QgsFields(poly_layer.fields())
        output_fields.append(QgsField("PARENT_FID", QMetaType.Type.LongLong))
        output_fields.append(QgsField("SUB_ID", QMetaType.Type.Int))

        # Use source CRS (even if undefined, preserve whatever is there)
        crs = poly_layer.crs()

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            output_fields,
            QgsWkbTypes.MultiPolygon,
            crs,
        )

        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT)
            )

        # Build spatial index on filtered line features
        feedback.pushInfo("Building spatial index on line features...")
        line_features = {}  # fid -> QgsFeature (with 2D geometry)
        line_index = QgsSpatialIndex()

        for feat in line_layer.getFeatures():
            if line_filter_field and line_filter_value:
                if str(feat[line_filter_field]) != line_filter_value:
                    continue
            geom = drop_zm(feat.geometry())
            if geom is None or geom.isEmpty():
                continue
            feat_copy = QgsFeature(feat)
            feat_copy.setGeometry(geom)
            line_features[feat.id()] = feat_copy
            line_index.addFeature(feat_copy)

        feedback.pushInfo(
            f"Indexed {len(line_features)} line features."
        )

        # Collect filtered polygon features
        polygon_features = []
        for feat in poly_layer.getFeatures():
            if poly_filter_field and poly_filter_value:
                if str(feat[poly_filter_field]) != poly_filter_value:
                    continue
            polygon_features.append(feat)

        total = len(polygon_features)
        feedback.pushInfo(f"Processing {total} polygon features...")

        split_count = 0
        unsplit_count = 0
        error_count = 0

        for i, poly_feat in enumerate(polygon_features):
            if feedback.isCanceled():
                break

            feedback.setProgress(int(100 * i / total) if total > 0 else 100)

            # Drop Z/M from polygon
            poly_geom = drop_zm(poly_feat.geometry())
            if poly_geom is None or poly_geom.isEmpty():
                error_count += 1
                feedback.reportError(
                    f"Feature {poly_feat.id()}: empty or null geometry, skipped."
                )
                continue

            fid = poly_feat.id()

            # Query spatial index for candidate lines
            candidate_ids = line_index.intersects(poly_geom.boundingBox())

            # Filter to actually intersecting lines
            intersecting_lines = []
            for cid in candidate_ids:
                line_feat = line_features[cid]
                if line_feat.geometry().intersects(poly_geom):
                    intersecting_lines.append(line_feat)

            if not intersecting_lines:
                # No lines: copy polygon as-is with SUB_ID=0
                out_feat = QgsFeature(output_fields)
                attrs = poly_feat.attributes() + [fid, 0]
                out_feat.setAttributes(attrs)
                out_geom = QgsGeometry(poly_geom)
                out_geom.convertToMultiType()
                out_feat.setGeometry(out_geom)
                sink.addFeature(out_feat, QgsFeatureSink.FastInsert)
                unsplit_count += 1
                continue

            # Convert to shapely and split
            try:
                from shapely.geometry import MultiPolygon as ShapelyMultiPolygon

                shapely_polygon = qgs_to_shapely(poly_geom)
                shapely_lines = [
                    qgs_to_shapely(lf.geometry()) for lf in intersecting_lines
                ]

                # Handle MultiPolygon (process each part)
                if isinstance(shapely_polygon, ShapelyMultiPolygon):
                    parts = list(shapely_polygon.geoms)
                else:
                    parts = [shapely_polygon]

                sub_id = 1
                did_split = False

                for part in parts:
                    sub_polygons = split_polygon_with_lines(
                        part, shapely_lines, snap_tolerance
                    )

                    if len(sub_polygons) > 1:
                        did_split = True

                    for sub_poly in sub_polygons:
                        out_feat = QgsFeature(output_fields)
                        out_geom = shapely_to_qgs(sub_poly)
                        out_geom.convertToMultiType()
                        if len(sub_polygons) == 1:
                            # This part was not split
                            attrs = poly_feat.attributes() + [fid, 0]
                        else:
                            attrs = poly_feat.attributes() + [fid, sub_id]
                            sub_id += 1
                        out_feat.setAttributes(attrs)
                        out_feat.setGeometry(out_geom)
                        sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

                if did_split:
                    split_count += 1
                else:
                    unsplit_count += 1

            except Exception as e:
                # On error, copy original polygon unchanged
                feedback.reportError(
                    f"Feature {fid}: split failed ({e}), copying original."
                )
                out_feat = QgsFeature(output_fields)
                attrs = poly_feat.attributes() + [fid, 0]
                out_feat.setAttributes(attrs)
                err_geom = QgsGeometry(poly_geom)
                err_geom.convertToMultiType()
                out_feat.setGeometry(err_geom)
                sink.addFeature(out_feat, QgsFeatureSink.FastInsert)
                error_count += 1

        feedback.pushInfo(
            f"Done. Split: {split_count}, Unsplit: {unsplit_count}, "
            f"Errors: {error_count}"
        )
        feedback.setProgress(100)

        return {self.OUTPUT: dest_id}
