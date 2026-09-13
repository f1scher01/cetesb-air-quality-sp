"""
Mapa coroplético das internações respiratórias no SUS por município da RMSP (PyQGIS).

Lê a camada integrada de analise_saude.py, classifica a taxa anualizada por 10 mil
habitantes em quebras naturais (Jenks), sobrepõe as estações da CETESB e exporta um
layout A4 e o projeto .qgz.

Uso (com o Python do QGIS):
    python qgis_mapa_saude.py

Autor: Lucas Fischer Paez
"""

import sys

import pandas as pd
from qgis.core import (
    QgsApplication, QgsClassificationJenks, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsLayoutExporter, QgsLayoutItemLegend, QgsLayoutItemMap,
    QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize, QgsMarkerSymbol, QgsPrintLayout, QgsProject,
    QgsRectangle, QgsStyle, QgsUnitTypes, QgsVectorLayer,
)

import config
from qgis_mapa import MM, rotulo_texto

GPKG = config.DIR_PROCESSADOS / "rmsp_saude_aod.gpkg"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def rotulo_competencia(aaaa_mm):
    ano, mes = aaaa_mm.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def camada_taxa():
    camada = QgsVectorLayer(f"{GPKG}|layername=rmsp_saude_aod", "Internações respiratórias por 10 mil hab./ano", "ogr")
    renderizador = QgsGraduatedSymbolRenderer("taxa_resp_10mil")
    renderizador.setSourceSymbol(QgsFillSymbol.createSimple({"outline_color": "#4a4a4a", "outline_width": "0.2"}))
    metodo = QgsClassificationJenks()
    metodo.setLabelPrecision(0)
    metodo.setLabelFormat("%1 a %2")
    renderizador.setClassificationMethod(metodo)
    renderizador.updateClasses(camada, 5)
    renderizador.updateColorRamp(QgsStyle.defaultStyle().colorRamp("Blues"))
    camada.setRenderer(renderizador)
    return camada


def camada_estacoes():
    camada = QgsVectorLayer(str(config.DIR_PROCESSADOS / "cetesb_estacoes.geojson"), "Estações CETESB com MP2,5", "ogr")
    camada.renderer().setSymbol(QgsMarkerSymbol.createSimple(
        {"name": "triangle", "color": "#f6ad55", "outline_color": "#1f1f1f", "outline_width": "0.25", "size": "2.6"}))
    return camada


def main():
    sih = pd.read_csv(config.DIR_PROCESSADOS / "sih_rmsp_internacoes.csv", usecols=["competencia"])
    inicio, fim, n = sih["competencia"].min(), sih["competencia"].max(), sih["competencia"].nunique()

    app = QgsApplication([], True)
    app.initQgis()
    try:
        projeto = QgsProject.instance()
        crs = QgsCoordinateReferenceSystem("EPSG:31983")
        projeto.setCrs(crs)
        taxa, estacoes = camada_taxa(), camada_estacoes()
        for camada in (taxa, estacoes):
            if not camada.isValid():
                sys.exit(f"Camada inválida: {camada.name()}")
            projeto.addMapLayer(camada)
        ano_pop = next(taxa.getFeatures())  # só para garantir leitura antes do layout
        del ano_pop

        layout = QgsPrintLayout(projeto)
        layout.initializeDefaults()
        layout.setName("RMSP internações respiratórias")

        mapa = QgsLayoutItemMap(layout)
        mapa.setCrs(crs)
        mapa.setLayers([estacoes, taxa])
        layout.addLayoutItem(mapa)
        mapa.attemptMove(QgsLayoutPoint(8, 24, MM))
        mapa.attemptResize(QgsLayoutSize(190, 160, MM))
        extensao = QgsCoordinateTransform(taxa.crs(), crs, projeto).transformBoundingBox(taxa.extent())
        extensao.scale(1.04)
        mapa.zoomToExtent(extensao)
        mapa.setFrameEnabled(True)

        rotulo_texto(layout, "Internações respiratórias no SUS por município de residência, RMSP", 8, 7, 15, negrito=True)
        rotulo_texto(layout, f"{n} competências, de {rotulo_competencia(inicio)} a {rotulo_competencia(fim)} · "
                             "CID-10 J00-J99, AIH do tipo 1 · taxa bruta anualizada · quebras naturais (Jenks)", 8, 15, 9.5)

        legenda = QgsLayoutItemLegend(layout)
        legenda.setLinkedMap(mapa)
        legenda.setTitle("Legenda")
        layout.addLayoutItem(legenda)
        legenda.attemptMove(QgsLayoutPoint(204, 24, MM))

        escala = QgsLayoutItemScaleBar(layout)
        escala.setStyle("Single Box")
        escala.setLinkedMap(mapa)
        escala.setUnits(QgsUnitTypes.DistanceKilometers)
        escala.setUnitLabel("km")
        escala.setUnitsPerSegment(10)
        escala.setNumberOfSegments(3)
        escala.setNumberOfSegmentsLeft(0)
        layout.addLayoutItem(escala)
        escala.attemptMove(QgsLayoutPoint(12, 172, MM))

        rotulo_texto(layout,
                     "Fontes: SIH/SUS (DATASUS, arquivos RDSP); IBGE, malha municipal e estimativa populacional (SIDRA 6579); "
                     "CETESB, estações da rede automática.\nTaxa bruta: não padronizada por idade e sem ajuste pela cobertura de "
                     "planos privados, que varia entre municípios. Não expressa efeito da poluição.\n"
                     "Projeção: SIRGAS 2000 / UTM 23S (EPSG:31983). Elaboração: Lucas Fischer Paez.",
                     8, 190, 7.5, largura=280)
        projeto.layoutManager().addLayout(layout)

        png = config.DIR_FIGURAS / "mapa_qgis_internacoes_resp.png"
        ajustes = QgsLayoutExporter.ImageExportSettings()
        ajustes.dpi = 200
        ajustes.generateWorldFile = False
        ajustes.exportMetadata = False
        if QgsLayoutExporter(layout).exportToImage(str(png), ajustes) != QgsLayoutExporter.Success:
            sys.exit("Falha ao exportar o layout.")
        qgz = config.RAIZ / "qgis" / "rmsp_saude.qgz"
        qgz.parent.mkdir(exist_ok=True)
        projeto.write(str(qgz))
        print(f"Mapa exportado: {png.relative_to(config.RAIZ)}")
        print(f"Projeto QGIS:   {qgz.relative_to(config.RAIZ)}")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
