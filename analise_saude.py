"""
Integração saúde × poluição por município da RMSP.

Junta, numa mesma camada municipal:
    - taxa de internações do SUS por 10 mil habitantes em 12 competências, por
      capítulo da CID-10 e para idosos (65+), a partir de sih_sus.py;
    - estatística zonal do AOD do GOES-19 (média e cobertura válida por município),
      a partir dos GeoTIFFs de goes_aod.py;
e produz a série mensal de internações da RMSP.

O que este módulo NÃO faz: estimar associação entre poluição e internação. Um scan
de satélite não representa a exposição de um ano, e a taxa bruta de internação no SUS
depende da cobertura de planos privados, da estrutura etária e do acesso hospitalar
de cada município. A camada integrada é a base sobre a qual um modelo (por exemplo,
série temporal com defasagem e ajuste por temperatura) seria construído.

Uso:
    python analise_saude.py

Saídas:
    dados/processados/rmsp_saude_aod.gpkg          camada municipal integrada
    dados/processados/rmsp_indicadores_municipais.csv
    figuras/sih_serie_mensal_rmsp.png

Autor: Lucas Fischer Paez
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from osgeo import gdal, ogr, osr

import config

gdal.UseExceptions()
ogr.UseExceptions()

GEOJSON = config.DIR_PROCESSADOS / "rmsp_municipios.geojson"
SIH = config.DIR_PROCESSADOS / "sih_rmsp_internacoes.csv"
GPKG = config.DIR_PROCESSADOS / "rmsp_saude_aod.gpkg"
CAP_RESP = "respiratorio (J00-J99)"
CAP_CIRC = "circulatorio (I00-I99)"


def estatistica_zonal(tif):
    """Média do AOD válido e fração de pixels válidos em cada município.

    Rasteriza os polígonos sobre a própria grade do GeoTIFF (critério do centro do
    pixel) e agrupa os valores pelo código do município.
    """
    raster = gdal.Open(str(tif))
    banda = raster.GetRasterBand(1)
    aod, nodata = banda.ReadAsArray(), banda.GetNoDataValue()

    zonas = gdal.GetDriverByName("MEM").Create("", raster.RasterXSize, raster.RasterYSize, 1, gdal.GDT_Int32)
    zonas.SetGeoTransform(raster.GetGeoTransform())
    zonas.SetProjection(raster.GetProjection())
    vetor = ogr.Open(str(GEOJSON))
    gdal.RasterizeLayer(zonas, [1], vetor.GetLayer(), options=["ATTRIBUTE=cod_ibge"])
    codigos = zonas.GetRasterBand(1).ReadAsArray()

    linhas = []
    for codigo in np.unique(codigos[codigos > 0]):
        dentro = codigos == codigo
        validos = dentro & (aod != nodata)
        linhas.append({
            "cod_ibge": int(codigo),
            "aod_media": float(aod[validos].mean()) if validos.any() else np.nan,
            "aod_pixels": int(dentro.sum()),
            "aod_validos_pct": round(100 * validos.sum() / dentro.sum(), 1),
        })
    return pd.DataFrame(linhas), raster.GetMetadata()["time_coverage_start"]


def indicadores_municipais(sih, municipios):
    """Taxas por 10 mil habitantes no conjunto das competências disponíveis."""
    n_comp = sih["competencia"].nunique()
    fator = 12 / n_comp                  # anualiza caso o período não tenha 12 meses

    def soma(filtro, nome):
        return sih[filtro].groupby("cod_ibge6")["internacoes"].sum().rename(nome)

    tabela = pd.concat([
        soma(sih["capitulo"] == CAP_RESP, "int_resp"),
        soma(sih["capitulo"] == CAP_CIRC, "int_circ"),
        soma((sih["capitulo"] == CAP_RESP) & (sih["faixa_etaria"] == "65+"), "int_resp_65mais"),
        soma((sih["capitulo"] == CAP_RESP) & (sih["faixa_etaria"] == "0-4"), "int_resp_0a4"),
        sih[sih["capitulo"] == CAP_RESP].groupby("cod_ibge6")["obitos"].sum().rename("obitos_resp"),
    ], axis=1).fillna(0).astype(int).reset_index()

    tabela = municipios.merge(tabela, how="left", left_on="cod_ibge6", right_on="cod_ibge6").fillna(0)
    for coluna in ("int_resp", "int_circ"):
        tabela[f"taxa_{coluna[4:]}_10mil"] = (tabela[coluna] * fator / tabela["pop_estimada"] * 1e4).round(1)
    tabela["letalidade_resp_pct"] = np.where(tabela["int_resp"] > 0,
                                             (100 * tabela["obitos_resp"] / tabela["int_resp"]).round(1), np.nan)
    return tabela, n_comp


def serie_mensal(sih):
    """Internações mensais na RMSP por mês de competência (mês de processamento da AIH)."""
    serie = sih.pivot_table(index="competencia", columns="capitulo", values="internacoes", aggfunc="sum").sort_index()
    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    for capitulo, cor in ((CAP_RESP, "#2b6cb0"), (CAP_CIRC, "#c05621")):
        ax.plot(serie.index, serie[capitulo], marker="o", ms=3.5, lw=1.6, color=cor, label=capitulo)
    ax.set_ylabel("Internações no SUS (AIH tipo 1)")
    ax.set_xlabel("Competência")
    ax.set_title("Residentes da RMSP: internações respiratórias e circulatórias por mês")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.text(0.01, 0.01, "Fonte: SIH/SUS (DATASUS), arquivos RDSP. Competência é o mês de processamento, não o da internação.",
             fontsize=6.5, color="0.35")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(config.DIR_FIGURAS / "sih_serie_mensal_rmsp.png")
    return serie


def gravar_gpkg(tabela, colunas):
    """Copia os polígonos do GeoJSON para um GeoPackage com os indicadores como atributos."""
    fonte = ogr.Open(str(GEOJSON))          # manter a referência: a camada morre junto com a fonte
    origem = fonte.GetLayer()
    GPKG.unlink(missing_ok=True)
    destino = ogr.GetDriverByName("GPKG").CreateDataSource(str(GPKG))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4674)
    camada = destino.CreateLayer("rmsp_saude_aod", srs, ogr.wkbMultiPolygon)
    for nome, tipo in colunas:
        camada.CreateField(ogr.FieldDefn(nome, tipo))

    por_codigo = tabela.set_index("cod_ibge")
    for feicao in origem:
        codigo = feicao.GetField("cod_ibge")
        nova = ogr.Feature(camada.GetLayerDefn())
        nova.SetGeometry(ogr.ForceToMultiPolygon(feicao.GetGeometryRef().Clone()))
        for nome, _ in colunas:
            valor = codigo if nome == "cod_ibge" else por_codigo.at[codigo, nome]
            if not (isinstance(valor, float) and np.isnan(valor)):
                nova.SetField(nome, valor.item() if hasattr(valor, "item") else valor)
        camada.CreateFeature(nova)
    destino = None


def main():
    fonte = ogr.Open(str(GEOJSON))
    municipios = pd.DataFrame([
        {"cod_ibge": f.GetField("cod_ibge"), "nome": f.GetField("nome"), "pop_estimada": f.GetField("pop_estimada")}
        for f in fonte.GetLayer()
    ])
    fonte = None
    municipios["cod_ibge6"] = municipios["cod_ibge"].astype(str).str[:6]

    sih = pd.read_csv(SIH, dtype={"cod_ibge6": str})
    tabela, n_comp = indicadores_municipais(sih, municipios)

    tifs = sorted(config.DIR_PROCESSADOS.glob("goes19_aod_rmsp_*.tif"))
    zonal = []
    for tif in tifs:
        z, inicio = estatistica_zonal(tif)
        zonal.append(z.assign(inicio_scan=inicio))
    zonal = pd.concat(zonal)
    melhor = zonal.groupby("inicio_scan")["aod_validos_pct"].mean().idxmax()   # scan com maior cobertura
    tabela = tabela.merge(zonal[zonal["inicio_scan"] == melhor].drop(columns="inicio_scan"), on="cod_ibge", how="left")

    tabela.drop(columns="cod_ibge6").to_csv(config.DIR_PROCESSADOS / "rmsp_indicadores_municipais.csv",
                                            index=False, encoding="utf-8")
    colunas = [("cod_ibge", ogr.OFTInteger), ("nome", ogr.OFTString), ("pop_estimada", ogr.OFTInteger),
               ("int_resp", ogr.OFTInteger), ("int_circ", ogr.OFTInteger), ("int_resp_65mais", ogr.OFTInteger),
               ("int_resp_0a4", ogr.OFTInteger), ("obitos_resp", ogr.OFTInteger),
               ("taxa_resp_10mil", ogr.OFTReal), ("taxa_circ_10mil", ogr.OFTReal), ("letalidade_resp_pct", ogr.OFTReal),
               ("aod_media", ogr.OFTReal), ("aod_validos_pct", ogr.OFTReal)]
    gravar_gpkg(tabela, colunas)
    serie = serie_mensal(sih)

    rmsp_resp, rmsp_pop = tabela["int_resp"].sum(), tabela["pop_estimada"].sum()
    print(f"{n_comp} competências ({sih['competencia'].min()} a {sih['competencia'].max()})")
    print(f"RMSP: {int(rmsp_resp)} internações respiratórias, "
          f"{rmsp_resp * 12 / n_comp / rmsp_pop * 1e4:.1f} por 10 mil hab./ano")
    print(f"Mês com mais internações respiratórias: {serie[CAP_RESP].idxmax()} ({int(serie[CAP_RESP].max())})")
    print(f"Zonal AOD: scan {melhor}, {tabela['aod_media'].notna().sum()} municípios com pixel válido")
    print(tabela.sort_values("taxa_resp_10mil", ascending=False)[["nome", "pop_estimada", "int_resp", "taxa_resp_10mil", "aod_media"]].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
