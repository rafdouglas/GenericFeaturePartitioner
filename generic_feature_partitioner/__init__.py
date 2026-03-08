from .partitioner_provider import GenericFeaturePartitionerProvider


class GenericFeaturePartitionerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        self.provider = GenericFeaturePartitionerProvider()
        from qgis.core import QgsApplication
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        if self.provider:
            from qgis.core import QgsApplication
            QgsApplication.processingRegistry().removeProvider(self.provider)


def classFactory(iface):
    return GenericFeaturePartitionerPlugin(iface)
