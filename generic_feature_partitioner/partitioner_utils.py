"""
Core geometry utilities for splitting polygons with partition lines.

Uses shapely 2.x for the topology/polygonize approach:
1. Extract polygon boundary as linestrings
2. Clip partition lines to polygon
3. Merge, snap, node all linework
4. Polygonize to create sub-polygons
5. Filter results by containment in original polygon
"""

from qgis.core import QgsGeometry, QgsWkbTypes

try:
    from shapely import wkb as shapely_wkb
    from shapely.geometry import (
        LineString,
        MultiLineString,
        MultiPolygon,
        Polygon,
    )
    from shapely.ops import polygonize, snap, unary_union

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


def drop_zm(geom):
    """Convert any ZM/Z/M geometry to 2D using QgsGeometry drop methods."""
    if geom is None or geom.isEmpty():
        return geom

    wkb_type = geom.wkbType()
    if QgsWkbTypes.hasZ(wkb_type) or QgsWkbTypes.hasM(wkb_type):
        geom_2d = QgsGeometry(geom.constGet().clone())
        geom_2d.get().dropZValue()
        geom_2d.get().dropMValue()
        return geom_2d
    return geom


def qgs_to_shapely(geom):
    """Convert QgsGeometry to shapely geometry via WKB."""
    return shapely_wkb.loads(bytes(geom.asWkb()))


def shapely_to_qgs(geom):
    """Convert shapely geometry to QgsGeometry via WKB."""
    qgs_geom = QgsGeometry()
    qgs_geom.fromWkb(geom.wkb)
    return qgs_geom


def _extract_boundary_lines(polygon):
    """Extract all boundary linestrings from a shapely Polygon.

    For polygons with holes, returns the exterior ring plus all interior rings
    as separate LineStrings.
    """
    lines = [LineString(polygon.exterior.coords)]
    for interior in polygon.interiors:
        lines.append(LineString(interior.coords))
    return lines


def _clip_and_filter_lines(lines, polygon, snap_tolerance):
    """Clip lines to polygon and filter out degenerate results.

    Returns only LineString results with length >= snap_tolerance.
    """
    clipped = []
    for line in lines:
        try:
            intersection = polygon.intersection(line)
        except Exception:
            continue

        if intersection.is_empty:
            continue

        # Extract LineStrings from the intersection result
        if isinstance(intersection, LineString):
            if intersection.length >= snap_tolerance:
                clipped.append(intersection)
        elif isinstance(intersection, MultiLineString):
            for part in intersection.geoms:
                if isinstance(part, LineString) and part.length >= snap_tolerance:
                    clipped.append(part)
        elif hasattr(intersection, "geoms"):
            # GeometryCollection - extract any LineStrings
            for part in intersection.geoms:
                if isinstance(part, LineString) and part.length >= snap_tolerance:
                    clipped.append(part)

    return clipped


def split_polygon_with_lines(polygon, lines, snap_tolerance=0.01):
    """Split a polygon using partition lines via topology/polygonize.

    Args:
        polygon: shapely Polygon to split
        lines: list of shapely LineStrings (partition lines)
        snap_tolerance: snapping tolerance in map units (default 0.01m)

    Returns:
        list of shapely Polygons (sub-polygons). If no valid split is
        possible, returns [polygon].
    """
    if not lines:
        return [polygon]

    # 1. Extract polygon boundary as linestrings
    boundary_lines = _extract_boundary_lines(polygon)

    # 2. Clip lines to polygon and filter degenerate results
    clipped_lines = _clip_and_filter_lines(lines, polygon, snap_tolerance)

    if not clipped_lines:
        return [polygon]

    # 3. Merge boundary + clipped lines
    all_lines = boundary_lines + clipped_lines

    # 4. Snap clipped lines to the boundary for better topology
    boundary_union = unary_union(boundary_lines)
    snapped_lines = []
    for line in all_lines:
        snapped = snap(line, boundary_union, snap_tolerance)
        snapped_lines.append(snapped)

    # 5. Node everything at intersections via unary_union
    noded = unary_union(snapped_lines)

    # 6. Polygonize the noded linework
    result_polygons = list(polygonize(noded))

    if not result_polygons:
        return [polygon]

    # 7. Filter: keep only sub-polygons inside the original polygon
    #    Use prepared geometry for faster containment checks
    from shapely.prepared import prep
    prepared_polygon = prep(polygon)

    min_area = snap_tolerance * snap_tolerance
    valid_sub_polygons = []
    for sub_poly in result_polygons:
        # Skip slivers
        if sub_poly.area < min_area:
            continue
        # Check that the sub-polygon's representative point is inside the original
        rep_point = sub_poly.representative_point()
        if prepared_polygon.contains(rep_point):
            valid_sub_polygons.append(sub_poly)

    if not valid_sub_polygons:
        return [polygon]

    # 8. If we only got one polygon back and it's essentially the same area,
    #    the lines didn't actually split anything
    if len(valid_sub_polygons) == 1:
        area_ratio = valid_sub_polygons[0].area / polygon.area
        if area_ratio > 0.99:
            return [polygon]

    return valid_sub_polygons
