# Script de Automação para o Console Python do QGIS
# Carrega automaticamente a camada GeoJSON e aplica estilo de quebras naturais
import os
from qgis.core import QgsVectorLayer, QgsProject

geojson_path = os.path.abspath("cetesb_estacoes_qualidade_ar.geojson")
layer = QgsVectorLayer(geojson_path, "Estacoes CETESB - Qualidade do Ar", "ogr")

if not layer.isValid():
    print("Erro ao carregar a camada GeoJSON!")
else:
    QgsProject.instance().addMapLayer(layer)
    print("Camada CETESB carregada com sucesso no QGIS!")
