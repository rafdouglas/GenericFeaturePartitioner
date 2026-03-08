from qgis.core import QgsProcessingProvider
from .partitioner_algorithm import SplitPolygonsAlgorithm


class GenericFeaturePartitionerProvider(QgsProcessingProvider):

    def id(self):
        return "generic_feature_partitioner"

    def name(self):
        return "Generic Feature Partitioner"

    def longName(self):
        return "Generic Feature Partitioner"

    def loadAlgorithms(self):
        self.addAlgorithm(SplitPolygonsAlgorithm())
