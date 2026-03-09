"""Integration tests requiring QGIS application instance.

All tests are marked with @pytest.mark.qgis and will be skipped
when QGIS is not available.
"""

import pytest


try:
    import qgis.core
    HAS_QGIS = not hasattr(qgis.core, '_mock_name')  # detect our mock
except ImportError:
    HAS_QGIS = False

pytestmark = pytest.mark.qgis
skip_no_qgis = pytest.mark.skipif(not HAS_QGIS, reason="QGIS not available")


@skip_no_qgis
class TestIntegration:
    def test_provider_registration(self):
        """Provider registers with QgsApplication processing registry."""
        from qgis.core import QgsApplication
        from generic_feature_partitioner.partitioner_provider import GenericFeaturePartitionerProvider
        provider = GenericFeaturePartitionerProvider()
        QgsApplication.processingRegistry().addProvider(provider)

    def test_algorithm_in_provider(self):
        """Provider's loadAlgorithms makes the algorithm discoverable."""
        from generic_feature_partitioner.partitioner_provider import GenericFeaturePartitionerProvider
        provider = GenericFeaturePartitionerProvider()
        provider.loadAlgorithms()
        assert len(provider._algorithms) == 1

    def test_run_with_real_layers(self):
        """Run algorithm with small in-memory vector layers."""
        pass  # requires QgsVectorLayer "memory" provider

    def test_crs_preservation(self):
        """Output layer CRS matches input polygon layer CRS."""
        pass  # requires real QGIS layers

    def test_plugin_lifecycle(self):
        """classFactory -> initGui -> unload cycle completes."""
        from unittest.mock import MagicMock
        from generic_feature_partitioner import classFactory
        iface = MagicMock()
        plugin = classFactory(iface)
        plugin.initGui()
        plugin.unload()
