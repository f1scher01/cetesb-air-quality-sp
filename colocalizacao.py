"""
Colocalização entre AOD do GOES-19 e MP2,5 das estações da CETESB.

Para cada GeoTIFF gerado por goes_aod.py:
    1. identifica a hora UTC do scan;
    2. seleciona as estações com MP2,5 naquela mesma hora;
    3. extrai a mediana dos pixels válidos numa janela 3x3 (~6 km) centrada na
       estação, exigindo pelo menos 3 pixels válidos;
    4. registra o par (AOD, MP2,5 estimado) e calcula as estatísticas do conjunto.

Limitações que o resultado carrega (e que o README repete):
    - AOD é coluna integrada instantânea; MP2,5 é concentração de superfície. A
      relação depende da altura da camada limite e da umidade, que não entram aqui.
    - O valor da CETESB é o índice invertido para µg/m³ (ver config.py), e o
      índice horário tende a refletir média móvel de 24 h, não a hora do scan.
    - Pixels na borda de nuvem costumam superestimar AOD; a exigência de 3 pixels
      válidos na janela atenua, mas não elimina, esse viés.
    Por isso a saída é um estudo de caso de colocalização, não uma calibração.

Uso:
    python colocalizacao.py

Saídas:
    dados/processados/colocalizacao_goes_cetesb.csv
    figuras/colocalizacao_aod_mp25.png

Autor: Lucas Fischer Paez
"""

from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from osgeo import gdal
from scipy import stats

import config

gdal.UseExceptions()

JANELA = 1                 # meia-largura em pixels: 1 -> janela 3x3
MIN_PIXELS_VALIDOS = 3


def amostrar_janela(raster, lon, lat):
    """Mediana dos pixels válidos na janela ao redor da coordenada, e quantos eram válidos."""
    x0, dx, _, y0, _, dy = raster["transformacao"]
    col, lin = int((lon - x0) / dx), int((lat - y0) / dy)
    matriz = raster["matriz"]
    if not (JANELA <= lin < matriz.shape[0] - JANELA and JANELA <= col < matriz.shape[1] - JANELA):
        return np.nan, 0
    recorte = matriz[lin - JANELA:lin + JANELA + 1, col - JANELA:col + JANELA + 1]
    validos = recorte[recorte != raster["nodata"]]
    if validos.size < MIN_PIXELS_VALIDOS:
        return np.nan, int(validos.size)
    return float(np.median(validos)), int(validos.size)


def ler_raster(caminho):
    ds = gdal.Open(str(caminho))
    banda = ds.GetRasterBand(1)
    inicio = ds.GetMetadata()["time_coverage_start"]
    return {
        "matriz": banda.ReadAsArray(),
        "nodata": banda.GetNoDataValue(),
        "transformacao": ds.GetGeoTransform(),
        "hora_utc": pd.Timestamp(datetime.strptime(inicio[:13], "%Y-%m-%dT%H"), tz="UTC"),
        "inicio_scan": inicio,
    }


def main():
    serie = pd.read_csv(config.DIR_PROCESSADOS / "cetesb_serie_horaria.csv", parse_dates=["datahora_utc"])
    mp25 = serie[(serie["poluente"] == "MP2.5") & serie["conc_ug_m3_estimada"].notna()]
    b = config.BBOX_RMSP
    mp25 = mp25[mp25["lon"].between(b["lon_min"], b["lon_max"]) & mp25["lat"].between(b["lat_min"], b["lat_max"])]

    pares = []
    for tif in sorted(config.DIR_PROCESSADOS.glob("goes19_aod_rmsp_*.tif")):
        raster = ler_raster(tif)
        estacoes = mp25[mp25["datahora_utc"] == raster["hora_utc"]]
        if estacoes.empty:
            print(f"{tif.name}: sem dado da CETESB para {raster['hora_utc']:%d/%m %H}h UTC")
            continue
        for _, e in estacoes.iterrows():
            aod, n = amostrar_janela(raster, e["lon"], e["lat"])
            pares.append({
                "inicio_scan_utc": raster["inicio_scan"], "estacao": e["estacao"],
                "lon": e["lon"], "lat": e["lat"], "aod_mediana_3x3": aod, "pixels_validos": n,
                "indice_cetesb": e["indice"], "mp25_ug_m3_estimada": e["conc_ug_m3_estimada"],
            })
        usados = sum(1 for p in pares if p["inicio_scan_utc"] == raster["inicio_scan"] and not np.isnan(p["aod_mediana_3x3"]))
        print(f"{tif.name}: {len(estacoes)} estações com MP2,5, {usados} com AOD válido")

    tabela = pd.DataFrame(pares)
    tabela.to_csv(config.DIR_PROCESSADOS / "colocalizacao_goes_cetesb.csv", index=False, encoding="utf-8")
    validos = tabela.dropna(subset=["aod_mediana_3x3"])
    if len(validos) < 5:
        print(f"Apenas {len(validos)} pares válidos; estatística não calculada.")
        return

    r, p_r = stats.pearsonr(validos["aod_mediana_3x3"], validos["mp25_ug_m3_estimada"])
    rho, p_rho = stats.spearmanr(validos["aod_mediana_3x3"], validos["mp25_ug_m3_estimada"])
    ajuste = stats.linregress(validos["aod_mediana_3x3"], validos["mp25_ug_m3_estimada"])
    print(f"n = {len(validos)} | Pearson r = {r:.2f} (p = {p_r:.3f}) | Spearman ρ = {rho:.2f} (p = {p_rho:.3f})")
    print(f"MP2,5 ≈ {ajuste.intercept:.1f} + {ajuste.slope:.1f}·AOD")

    config.DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5), dpi=200)
    for inicio, grupo in validos.groupby("inicio_scan_utc"):
        ax.scatter(grupo["aod_mediana_3x3"], grupo["mp25_ug_m3_estimada"], s=28, alpha=0.8,
                   label=f"scan {inicio[8:10]}/{inicio[5:7]} {inicio[11:16]} UTC")
    xs = np.linspace(validos["aod_mediana_3x3"].min(), validos["aod_mediana_3x3"].max(), 50)
    ax.plot(xs, ajuste.intercept + ajuste.slope * xs, color="0.25", lw=1, ls="--",
            label=f"MQO: r = {r:.2f}, ρ = {rho:.2f}, n = {len(validos)}")
    ax.set_xlabel("AOD 550 nm — GOES-19 ABI (mediana 3×3, DQF ≤ 1)")
    ax.set_ylabel("MP2,5 estimado a partir do índice CETESB (µg/m³)")
    ax.set_title("Colocalização satélite × superfície na RMSP")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(config.DIR_FIGURAS / "colocalizacao_aod_mp25.png")
    print("Figura gravada em figuras/colocalizacao_aod_mp25.png")


if __name__ == "__main__":
    main()
