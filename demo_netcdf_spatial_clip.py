"""
Recorte espacial sobre grade SINTETICA, no formato de um produto NetCDF.

ATENCAO: este modulo NAO le arquivos NetCDF ou HDF5 reais. A grade e gerada em
memoria com numpy.random e semente fixa, apenas para exercitar a mecanica de
recorte espacial e extracao de pixel por coordenada.

As metricas RMSE, MAE e vies calculadas ao final comparam ruido sintetico contra
os valores literais das estacoes definidos em pipeline_cetesb_sp.py. Elas sao
aritmeticamente corretas e nao possuem significado fisico. Nao interprete o
resultado como validacao de satelite contra medicao de superficie.

Substituir a funcao simular_grade_satelite_maia() por leitura real com xarray
e o proximo passo do projeto (ver secao "Proximos passos" do README).

Autor: Lucas Fischer Paez
"""

import os

import numpy as np
import pandas as pd


def simular_grade_satelite_maia(n_lat=50, n_lon=50):
    """
    Gera uma matriz sintetica com a forma de um produto orbital de AOD.

    O campo base decai exponencialmente a partir do centro urbano, simulando um
    gradiente de emissao, e recebe ruido gaussiano. Nao ha dado de satelite aqui.

    Retorna:
        lats  -- vetor de latitudes (graus, WGS84)
        lons  -- vetor de longitudes (graus, WGS84)
        campo -- matriz (n_lat, n_lon) de PM2.5 sintetico em ug/m3
    """
    print("-> Gerando grade SINTETICA no formato de produto orbital (nao e dado real)...")
    lats = np.linspace(-23.85, -23.40, n_lat)
    lons = np.linspace(-46.85, -46.40, n_lon)

    lon_grid, lat_grid = np.meshgrid(lons, lats)
    centro_lat, centro_lon = -23.55, -46.63
    dist = np.sqrt((lat_grid - centro_lat) ** 2 + (lon_grid - centro_lon) ** 2)

    campo_base = 14.0 + 10.0 * np.exp(-dist / 0.12)

    rng = np.random.default_rng(42)
    ruido = rng.normal(0.0, 1.2, size=(n_lat, n_lon))

    return lats, lons, np.clip(campo_base + ruido, 5.0, 50.0)


def extrair_ponto_mais_proximo(lats, lons, matriz, lat_alvo, lon_alvo):
    """Extrai o valor do pixel mais proximo de uma coordenada geografica."""
    idx_lat = int(np.abs(lats - lat_alvo).argmin())
    idx_lon = int(np.abs(lons - lon_alvo).argmin())
    return matriz[idx_lat, idx_lon]


def calibrar_satelite_com_cetesb(csv_path="cetesb_estacoes_qualidade_ar.csv"):
    """
    Extrai o pixel sintetico na coordenada de cada estacao e calcula residuos.

    As metricas resultantes comparam duas fontes sinteticas e nao constituem
    validacao. Mantidas para demonstrar a mecanica de comparacao ponto a ponto.
    """
    lats, lons, campo_sintetico = simular_grade_satelite_maia()

    if not os.path.exists(csv_path):
        print(f"Arquivo '{csv_path}' nao encontrado.")
        print("Execute antes: python pipeline_cetesb_sp.py")
        return None

    df = pd.read_csv(csv_path)

    df["pm25_grade_sintetica"] = [
        round(extrair_ponto_mais_proximo(lats, lons, campo_sintetico, lat, lon), 2)
        for lat, lon in zip(df["latitude"], df["longitude"])
    ]
    df["residuo"] = (df["pm25_grade_sintetica"] - df["pm25_medio"]).round(2)

    rmse = float(np.sqrt(np.mean(df["residuo"] ** 2)))
    mae = float(np.mean(np.abs(df["residuo"])))
    vies = float(np.mean(df["residuo"]))

    print("\n" + "=" * 60)
    print("  RESIDUOS ENTRE DUAS FONTES SINTETICAS (sem significado fisico)")
    print("=" * 60)
    print(f"  Estacoes avaliadas : {len(df)}")
    print(f"  MAE                : {mae:.2f} ug/m3")
    print(f"  RMSE               : {rmse:.2f} ug/m3")
    print(f"  Vies medio         : {vies:+.2f} ug/m3")
    print("=" * 60 + "\n")

    saida = "validacao_satelite_cetesb.csv"
    df[["estacao", "municipio", "pm25_medio", "pm25_grade_sintetica", "residuo"]].to_csv(
        saida, index=False, encoding="utf-8-sig"
    )
    print(f"[OK] Tabela de residuos exportada: {saida}")

    return df


if __name__ == "__main__":
    calibrar_satelite_com_cetesb()
