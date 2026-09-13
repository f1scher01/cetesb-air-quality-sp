"""
Montagem automatizada do mapa no QGIS (PyQGIS, sem abrir a interface).

Carrega o GeoTIFF de AOD de um scan, os limites municipais da RMSP e as estações
da CETESB daquela hora; aplica simbologia (rampa contínua no raster, classes
graduadas de MP2,5 nas estações); compõe um layout A4 com legenda, barra de
escala e fontes; exporta PNG e salva o projeto .qgz para edição manual.

O projeto usa SIRGAS 2000 / UTM 23S (EPSG:31983) para que a barra de escala
seja métrica. As camadas continuam em coordenadas geográficas e são reprojetadas
em tempo de renderização.

Uso (com o Python do QGIS):
    python qgis_mapa.py                      # scan com mais pares válidos
    python qgis_mapa.py 2026-09-11T19:00     # prefixo do início do scan, UTC

Pré-requisitos: goes_aod.py, coleta_cetesb.py, limites_ibge.py e colocalizacao.py.

Autor: Lucas Fischer Paez
"""

import os
import sys

# No Windows a plataforma nativa renderiza fontes sem abrir janela; "offscreen"
# nao carrega o banco de fontes e o texto do layout sai como blocos.
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from osgeo import gdal
from qgis.core import (
    QgsApplication, QgsColorRampShader, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsFeature, QgsField, QgsFillSymbol, QgsGeometry, QgsGraduatedSymbolRenderer, QgsLayoutExporter,
    QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemScaleBar, QgsLayoutPoint,
    QgsLayoutSize, QgsMarkerSymbol, QgsPointXY, QgsPrintLayout, QgsProject, QgsRasterLayer,
    QgsRasterShader, QgsRectangle, QgsRendererRange, QgsSingleBandPseudoColorRenderer, QgsStyle,
    QgsMapLayerLegendUtils, QgsTextFormat, QgsUnitTypes, QgsVectorFileWriter, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont

import config

gdal.UseExceptions()
MM = QgsUnitTypes.LayoutMillimeters

# Classes de MP2,5 (µg/m³). O corte em 15 é o valor-guia de 24 h da OMS (2021),
# também adotado como padrão final pela Resolução CONAMA 506/2024.
CLASSES_MP25 = [
    (0, 5, "0 – 5", "#1a9850"),
    (5, 10, "5 – 10", "#91cf60"),
    (10, 15, "10 – 15", "#fee08b"),
    (15, 25, "15 – 25 (> guia OMS 24 h)", "#fc8d59"),
    (25, 1000, "> 25", "#d73027"),
]
AOD_MIN, AOD_MAX = 0.0, 0.4


def escolher_scan(pares, prefixo):
    validos = pares.dropna(subset=["aod_mediana_3x3"])
    if prefixo:
        escolhidos = validos[validos["inicio_scan_utc"].str.startswith(prefixo)]
        if escolhidos.empty:
            sys.exit(f"Nenhum par válido para o scan {prefixo}.")
        return escolhidos["inicio_scan_utc"].iloc[0]
    return validos["inicio_scan_utc"].value_counts().idxmax()


def raster_do_scan(inicio):
    for tif in config.DIR_PROCESSADOS.glob("goes19_aod_rmsp_*.tif"):
        if gdal.Open(str(tif)).GetMetadata().get("time_coverage_start") == inicio:
            return tif
    sys.exit(f"GeoTIFF do scan {inicio} não encontrado.")


def camada_aod(tif):
    camada = QgsRasterLayer(str(tif), "AOD 550 nm, GOES-19")
    rampa = QgsStyle.defaultStyle().colorRamp("Magma")
    funcao = QgsColorRampShader(AOD_MIN, AOD_MAX, rampa)
    funcao.setColorRampType(QgsColorRampShader.Interpolated)
    funcao.classifyColorRamp(9, 1)
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(funcao)
    renderizador = QgsSingleBandPseudoColorRenderer(camada.dataProvider(), 1, shader)
    renderizador.setClassificationMin(AOD_MIN)
    renderizador.setClassificationMax(AOD_MAX)
    camada.setRenderer(renderizador)
    camada.setOpacity(0.9)
    return camada


def camada_municipios():
    camada = QgsVectorLayer(str(config.DIR_PROCESSADOS / "rmsp_municipios.geojson"), "Municípios da RMSP (IBGE)", "ogr")
    camada.renderer().setSymbol(QgsFillSymbol.createSimple(
        {"color": "0,0,0,0", "outline_color": "#6b6b6b", "outline_width": "0.25"}))
    return camada


def camada_estacoes(pares_scan, rotulo):
    """Grava as estações do scan num GeoPackage e carrega com simbologia graduada."""
    memoria = QgsVectorLayer("Point?crs=EPSG:4674", "estacoes", "memory")
    provedor = memoria.dataProvider()
    provedor.addAttributes([QgsField("estacao", QVariant.String), QgsField("mp25_ug_m3", QVariant.Double),
                            QgsField("aod", QVariant.Double)])
    memoria.updateFields()
    for _, p in pares_scan.iterrows():
        f = QgsFeature(memoria.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["lon"], p["lat"])))
        f.setAttributes([p["estacao"], float(p["mp25_ug_m3_estimada"]),
                         None if pd.isna(p["aod_mediana_3x3"]) else float(p["aod_mediana_3x3"])])
        provedor.addFeature(f)

    gpkg = config.DIR_PROCESSADOS / f"estacoes_mp25_{rotulo}.gpkg"
    opcoes = QgsVectorFileWriter.SaveVectorOptions()
    opcoes.driverName = "GPKG"
    QgsVectorFileWriter.writeAsVectorFormatV3(memoria, str(gpkg), QgsProject.instance().transformContext(), opcoes)

    camada = QgsVectorLayer(str(gpkg), "MP2,5 CETESB (µg/m³)", "ogr")
    faixas = [QgsRendererRange(ini, fim, QgsMarkerSymbol.createSimple({
        "name": "circle", "color": cor, "outline_color": "#1f1f1f", "outline_width": "0.3", "size": "3.4"}), rotulo_faixa)
        for ini, fim, rotulo_faixa, cor in CLASSES_MP25]
    camada.setRenderer(QgsGraduatedSymbolRenderer("mp25_ug_m3", faixas))
    return camada


def rotulo_texto(layout, texto, x, y, tamanho, negrito=False, largura=None):
    item = QgsLayoutItemLabel(layout)
    formato = QgsTextFormat()
    fonte = QFont("Arial")
    fonte.setBold(negrito)
    formato.setFont(fonte)
    formato.setSize(tamanho)
    formato.setColor(QColor("#1f1f1f"))
    item.setTextFormat(formato)
    item.setText(texto)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    if largura:
        item.attemptResize(QgsLayoutSize(largura, 30, MM))
        item.adjustSizeToText()
    else:
        item.adjustSizeToText()
    return item


def montar_layout(projeto, inicio, n_pares, camadas, crs_mapa):
    layout = QgsPrintLayout(projeto)
    layout.initializeDefaults()          # A4 paisagem
    layout.setName("RMSP AOD x MP2,5")

    mapa = QgsLayoutItemMap(layout)
    mapa.setCrs(crs_mapa)
    mapa.setLayers(camadas)
    layout.addLayoutItem(mapa)
    mapa.attemptMove(QgsLayoutPoint(8, 24, MM))
    mapa.attemptResize(QgsLayoutSize(190, 160, MM))
    b = config.BBOX_RMSP
    extensao = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), crs_mapa, projeto).transformBoundingBox(
        QgsRectangle(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"]))
    mapa.zoomToExtent(extensao)
    mapa.setFrameEnabled(True)

    rotulo_texto(layout, "Profundidade óptica de aerossóis (GOES-19) e MP2,5 de superfície (CETESB) — RMSP", 8, 7, 15, negrito=True)
    rotulo_texto(layout, f"Scan de {inicio[8:10]}/{inicio[5:7]}/{inicio[:4]} às {inicio[11:16]} UTC · "
                         f"{n_pares} estações com AOD válido na janela 3×3 · pixels com DQF > 1 removidos", 8, 15, 9.5)

    legenda = QgsLayoutItemLegend(layout)
    legenda.setLinkedMap(mapa)
    legenda.setTitle("Legenda")
    layout.addLayoutItem(legenda)
    legenda.attemptMove(QgsLayoutPoint(204, 24, MM))
    # Remove o nó de texto "Band 1: ..." do raster e deixa só a rampa de cores.
    legenda.setAutoUpdateModel(False)
    for no in legenda.model().rootGroup().findLayers():
        if no.layer() is camadas[-1]:
            QgsMapLayerLegendUtils.setLegendNodeOrder(no, [1])
            legenda.model().refreshLayerLegend(no)

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
                 "Fontes: NOAA GOES-19 ABI L2+ AOD (ABI-L2-AODF, NOAA Open Data Dissemination); CETESB, serviço ArcGIS do QUALAR; "
                 "IBGE, malha municipal.\nMP2,5 estimado pela inversão do índice de qualidade do ar publicado (ver config.py). "
                 "AOD é coluna integrada instantânea; MP2,5 é superfície. Estudo de caso, não calibração.\n"
                 "Projeção: SIRGAS 2000 / UTM 23S (EPSG:31983). Elaboração: Lucas Fischer Paez.",
                 8, 190, 7.5, largura=280)
    return layout


def main():
    prefixo = sys.argv[1] if len(sys.argv) > 1 else None
    pares = pd.read_csv(config.DIR_PROCESSADOS / "colocalizacao_goes_cetesb.csv")
    inicio = escolher_scan(pares, prefixo)
    pares_scan = pares[pares["inicio_scan_utc"] == inicio]
    n_validos = int(pares_scan["aod_mediana_3x3"].notna().sum())
    rotulo = inicio[:16].replace("-", "").replace(":", "")

    app = QgsApplication([], True)
    app.initQgis()
    try:
        projeto = QgsProject.instance()
        crs_mapa = QgsCoordinateReferenceSystem("EPSG:31983")
        projeto.setCrs(crs_mapa)

        aod = camada_aod(raster_do_scan(inicio))
        municipios = camada_municipios()
        estacoes = camada_estacoes(pares_scan, rotulo)
        for camada in (aod, municipios, estacoes):
            if not camada.isValid():
                sys.exit(f"Camada inválida: {camada.name()}")
            projeto.addMapLayer(camada)

        layout = montar_layout(projeto, inicio, n_validos, [estacoes, municipios, aod], crs_mapa)
        projeto.layoutManager().addLayout(layout)

        config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
        png = config.DIR_FIGURAS / "mapa_qgis_aod_mp25.png"
        ajustes = QgsLayoutExporter.ImageExportSettings()
        ajustes.dpi = 200
        ajustes.generateWorldFile = False
        ajustes.exportMetadata = False
        resultado = QgsLayoutExporter(layout).exportToImage(str(png), ajustes)
        if resultado != QgsLayoutExporter.Success:
            sys.exit(f"Falha ao exportar o layout (código {resultado}).")

        qgz = config.RAIZ / "qgis" / "rmsp_aod_mp25.qgz"
        qgz.parent.mkdir(exist_ok=True)
        projeto.write(str(qgz))
        print(f"Scan {inicio}: {n_validos} estações com AOD válido")
        print(f"Mapa exportado: {png.relative_to(config.RAIZ)}")
        print(f"Projeto QGIS:   {qgz.relative_to(config.RAIZ)}")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
