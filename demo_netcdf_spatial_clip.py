"""
Simulacao de Pipeline Satelital: Ingestao, Recorte Espacial e Calibracao Ground-Truth
Modelagem conceitual dos produtos da Missao MAIA-NASA (NetCDF/HDF5) e Rede CETESB
Autor: Lucas Fischer Paez
"""

import json
import numpy as np
import pandas as pd

def simular_grade_satelite_maia(n_lat=50, n_lon=50):
    """
    Simula uma matriz tridimensional caracteristica de produtos NetCDF da NASA
    Dimensoes: (tempo, latitude, longitude)
    Resolucao espacial ~1 km sobre a Regiao Metropolitana de Sao Paulo
    """
    print("-> Simulando grade matricial de sensoriamento remoto (MAIA-NASA Level 2/3)...")
    lats = np.linspace(-23.85, -23.40, n_lat)
    lons = np.linspace(-46.85, -46.40, n_lon)
    
    # Modelo fisico: gradiente de emissao urbana central com decaimento para as bordas
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    centro_lat, centro_lon = -23.55, -46.63
    dist = np.sqrt((lat_grid - centro_lat)**2 + (lon_grid - centro_lon)**2)
    
    # Campo base de PM2.5 por dispersao atmosferica
    campo_base = 14.0 + 10.0 * np.exp(-dist / 0.12)
    
    # Ruido gaussiano simulando variabilidade de medicao optica de aerossol (AOD)
    np.random.seed(42)
    ruido = np.random.normal(0, 1.2, size=(n_lat, n_lon))
    satelite_pm25 = np.clip(campo_base + ruido, 5.0, 50.0)
    
    return lats, lons, satelite_pm25

def extrair_ponto_mais_proximo(lats, lons, matriz, lat_alvo, lon_alvo):
    """Recorte e extracao do pixel mais proximo da coordenada da estacao de superficie."""
    idx_lat = (np.abs(lats - lat_alvo)).argmin()
    idx_lon = (np.abs(lons - lon_alvo)).argmin()
    return matriz[idx_lat, idx_lon]

def calibrar_satelite_com_cetesb():
    lats, lons, satelite_pm25 = simular_grade_satelite_maia()
    
    # Carregar dados terrestres da CETESB
    csv_path = "cetesb_estacoes_qualidade_ar.csv"
    if not os.path.exists(csv_path):
        print("Execute primeiro pipeline_cetesb_sp.py para gerar os dados das estacoes.")
        return
        
    df_cetesb = pd.read_csv(csv_path)
    
    # Extrair valor estimado pelo satelite no pixel de cada estacao terrestre
    estimativas_satelite = []
    for _, row in df_cetesb.iterrows():
        val_sat = extrair_ponto_mais_proximo(
            lats, lons, satelite_pm25, row["latitude"], row["longitude"]
        )
        estimativas_satelite.append(round(val_sat, 2))
        
    df_cetesb["pm25_satelite_estimado"] = estimativas_satelite
    df_cetesb["erro_residual"] = round(df_cetesb["pm25_satelite_estimado"] - df_cetesb["pm25_medio"], 2)
    
    # Metricas estatisticas de calibracao
    rmse = np.sqrt(np.mean(df_cetesb["erro_residual"]**2))
    mae = np.mean(np.abs(df_cetesb["erro_residual"]))
    bias = np.mean(df_cetesb["erro_residual"])
    
    print("\n=======================================================")
    print("      RELATORIO DE VALIDACAO CRUZADA: SATELITE vs CETESB")
    print("=======================================================")
    print(f"Total de Estacoes Avaliadas: {len(df_cetesb)}")
    print(f"Erro Medio Absoluto (MAE):    {mae:.2f} ug/m3")
    print(f"Raiz do Erro Quadratico (RMSE): {rmse:.2f} ug/m3")
    print(f"Vies Medio (Bias):            {bias:+.2f} ug/m3")
    print("=======================================================\n")
    
    # Salvar tabela de calibracao
    out_calibracao = "validacao_satelite_cetesb.csv"
    df_cetesb[["estacao", "municipio", "pm25_medio", "pm25_satelite_estimado", "erro_residual"]].to_csv(
        out_calibracao, index=False, encoding="utf-8-sig"
    )
    print(f"[OK] Tabela de validacao cruzada exportada: {out_calibracao}")

if __name__ == "__main__":
    import os
    calibrar_satelite_com_cetesb()
