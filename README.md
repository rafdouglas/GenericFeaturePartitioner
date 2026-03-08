<p align="center">
  <img src="Generic_Feature_Partitioner.png" alt="Generic Feature Partitioner" width="200"/>
</p>

# Generic Feature Partitioner

**QGIS Processing plugin to split polygons along intersecting lines using topology-based polygonization.**

Split building footprints by internal walls, land parcels by boundaries, or any polygon layer using any line layer — with attribute filtering, snapping, and full batch support.

---

## How it works

For each polygon, the algorithm:

1. Finds intersecting lines via spatial index
2. Extracts the polygon boundary (exterior + interior rings)
3. Clips lines to the polygon, discarding degenerate results
4. Snaps all linework within a configurable tolerance
5. Nodes everything at intersections via `unary_union`
6. Runs `shapely.ops.polygonize` to create sub-polygons from the planar graph
7. Filters results by containment, discarding slivers

Dangling lines (dead-ends) are naturally ignored. Overshooting lines are clipped. Z/M coordinates are dropped to produce 2D output.

## Requirements

- QGIS >= 3.34
- shapely 2.x (bundled with QGIS)

## Installation

### From ZIP (recommended)

1. Download the latest `generic_feature_partitioner.zip` from [Releases](../../releases)
2. In QGIS: **Plugins > Manage and Install Plugins > Install from ZIP**
3. Select the downloaded ZIP file

### Symlink (development)

```bash
# Flatpak QGIS
ln -s /path/to/generic_feature_partitioner \
  ~/.var/app/org.qgis.qgis/data/QGIS/QGIS3/profiles/default/python/plugins/generic_feature_partitioner

# System QGIS
ln -s /path/to/generic_feature_partitioner \
  ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/generic_feature_partitioner
```

### Enable

In QGIS: **Plugins > Manage and Install Plugins > Installed** > check **generic_feature_partitioner**.

## Usage

The algorithm appears in the Processing Toolbox under:

**Generic Feature Partitioner > Vector geometry > Split Polygons with Partition Lines**

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Input polygon layer | Vector (Polygon) | — | Layer containing polygons to split |
| Input line layer | Vector (Line) | — | Layer containing partition lines |
| Polygon filter field | String | `NOME_CLAS` | Attribute field to filter polygons (optional) |
| Polygon filter value | String | `EDIFICATO` | Value to match for polygon filtering (optional) |
| Line filter field | String | `NOME_CLAS` | Attribute field to filter lines (optional) |
| Line filter value | String | `EDIFICATO` | Value to match for line filtering (optional) |
| Snap tolerance | Double | `0.01` | Snapping tolerance in map units |
| Output layer | Vector (MultiPolygon) | — | Output path (e.g. GeoPackage) |

Leave filter fields/values empty to process all features without filtering.

### Output fields

All original polygon attributes are preserved, plus:

| Field | Type | Description |
|-------|------|-------------|
| `PARENT_FID` | Integer64 | Original feature ID for traceability |
| `SUB_ID` | Integer | `0` = unsplit polygon, `1..N` = sub-polygon index |

### Batch processing

Right-click the algorithm in the Processing Toolbox and select **Execute as Batch Process** to run on multiple tiles simultaneously.

### Command line

```bash
qgis_process run generic_feature_partitioner:splitpolygonswithlines \
  --INPUT_POLYGONS=AREA.shp \
  --INPUT_LINES=LINE.shp \
  --POLYGON_FILTER_FIELD=NOME_CLAS \
  --POLYGON_FILTER_VALUE=EDIFICATO \
  --LINE_FILTER_FIELD=NOME_CLAS \
  --LINE_FILTER_VALUE=EDIFICATO \
  --SNAP_TOLERANCE=0.01 \
  --OUTPUT=output.gpkg
```

## Performance

Tested on Friuli Venezia Giulia regional cadastral data (QGIS 3.44):

| Tile | Input polygons | Output features | Time | Errors | Area conservation |
|------|---------------|-----------------|------|--------|-------------------|
| 066160 | 6,066 | 12,731 | 4.8s | 0 | exact |
| 066110 | 19,557 | 42,415 | 14.4s | 0 | exact |

## File structure

```
generic_feature_partitioner/
    __init__.py                # Plugin entry point (classFactory)
    metadata.txt               # QGIS plugin metadata
    partitioner_provider.py    # Processing provider registration
    partitioner_algorithm.py   # Algorithm: parameters, filtering, output
    partitioner_utils.py       # Core geometry: polygonize, snap, clip
```

## Author

**RafDouglas C. Tommasi** — [rafdouglas@gmail.com](mailto:rafdouglas@gmail.com) — [LinkedIn](https://www.linkedin.com/in/rafdouglas/)

## License

This plugin is provided as-is for use with QGIS.
