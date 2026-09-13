"""
Pipeline de Integração e Análise Geoespacial: Dados de Qualidade do Ar CETESB (RMSPO)
LEGADO SINTETICO: as concentracoes abaixo foram escritas a mao, nao vieram da CETESB.
Substituido por coleta_cetesb.py, que le dados reais do servico publico do QUALAR.
Autor: Lucas Fischer Paez
"""

import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# 1. Definição das Estações de Monitoramento CETESB na Grande São Paulo
# Coordenadas aproximadas das estacoes (WGS84). As concentracoes e contagens sao
# valores SINTETICOS de ordem de grandeza plausivel, nao medias historicas reais.
ESTACOES_CETESB = [
    {
        "estacao": "Pinheiros",
        "municipio": "São Paulo",
        "latitude": -23.5614,
        "longitude": -46.7020,
        "altitude_m": 725,
        "pm25_medio": 18.4,
        "pm10_medio": 33.2,
        "no2_medio": 38.5,
        "dias_ultrapassagem_oms": 58,
        "perfil": "Urbano / Tráfego Intenso"
    },
    {
        "estacao": "Cerqueira César",
        "municipio": "São Paulo",
        "latitude": -23.5535,
        "longitude": -46.6727,
        "altitude_m": 792,
        "pm25_medio": 20.1,
        "pm10_medio": 36.8,
        "no2_medio": 44.2,
        "dias_ultrapassagem_oms": 67,
        "perfil": "Urbano / Tráfego Intenso"
    },
    {
        "estacao": "Congonhas",
        "municipio": "São Paulo",
        "latitude": -23.6163,
        "longitude": -46.6635,
        "altitude_m": 780,
        "pm25_medio": 22.8,
        "pm10_medio": 41.5,
        "no2_medio": 49.0,
        "dias_ultrapassagem_oms": 76,
        "perfil": "Urbano / Aeroportuário"
    },
    {
        "estacao": "Parque D. Pedro II",
        "municipio": "São Paulo",
        "latitude": -23.5448,
        "longitude": -46.6277,
        "altitude_m": 725,
        "pm25_medio": 21.5,
        "pm10_medio": 39.4,
        "no2_medio": 46.8,
        "dias_ultrapassagem_oms": 71,
        "perfil": "Centro Urbano / Comercial"
    },
    {
        "estacao": "Santana",
        "municipio": "São Paulo",
        "latitude": -23.5050,
        "longitude": -46.6288,
        "altitude_m": 735,
        "pm25_medio": 17.6,
        "pm10_medio": 32.0,
        "no2_medio": 36.4,
        "dias_ultrapassagem_oms": 52,
        "perfil": "Residencial / Comercial"
    },
    {
        "estacao": "Mooca",
        "municipio": "São Paulo",
        "latitude": -23.5500,
        "longitude": -46.5986,
        "altitude_m": 730,
        "pm25_medio": 19.3,
        "pm10_medio": 35.7,
        "no2_medio": 41.0,
        "dias_ultrapassagem_oms": 63,
        "perfil": "Misto / Industrial Histórico"
    },
    {
        "estacao": "Grajaú - Parelheiros",
        "municipio": "São Paulo",
        "latitude": -23.7767,
        "longitude": -46.6953,
        "altitude_m": 790,
        "pm25_medio": 12.3,
        "pm10_medio": 24.1,
        "no2_medio": 21.5,
        "dias_ultrapassagem_oms": 31,
        "perfil": "Periférico / Mananciais"
    },
    {
        "estacao": "Interlagos",
        "municipio": "São Paulo",
        "latitude": -23.6806,
        "longitude": -46.6753,
        "altitude_m": 745,
        "pm25_medio": 15.8,
        "pm10_medio": 29.6,
        "no2_medio": 30.2,
        "dias_ultrapassagem_oms": 44,
        "perfil": "Urbano / Represa"
    },
    {
        "estacao": "Santo Amaro",
        "municipio": "São Paulo",
        "latitude": -23.6525,
        "longitude": -46.7094,
        "altitude_m": 730,
        "pm25_medio": 18.0,
        "pm10_medio": 34.0,
        "no2_medio": 39.5,
        "dias_ultrapassagem_oms": 56,
        "perfil": "Comercial / Eixo Viário"
    },
    {
        "estacao": "Itaquera",
        "municipio": "São Paulo",
        "latitude": -23.5800,
        "longitude": -46.4580,
        "altitude_m": 745,
        "pm25_medio": 16.9,
        "pm10_medio": 31.8,
        "no2_medio": 33.1,
        "dias_ultrapassagem_oms": 49,
        "perfil": "Residencial Periférico"
    },
    {
        "estacao": "Mauá",
        "municipio": "Mauá",
        "latitude": -23.6683,
        "longitude": -46.4614,
        "altitude_m": 770,
        "pm25_medio": 20.7,
        "pm10_medio": 38.5,
        "no2_medio": 43.0,
        "dias_ultrapassagem_oms": 69,
        "perfil": "Industrial / Polo Petroquímico"
    },
    {
        "estacao": "Santo André - Capuava",
        "municipio": "Santo André",
        "latitude": -23.6450,
        "longitude": -46.4950,
        "altitude_m": 760,
        "pm25_medio": 21.2,
        "pm10_medio": 39.1,
        "no2_medio": 45.2,
        "dias_ultrapassagem_oms": 73,
        "perfil": "Industrial / Polo Petroquímico"
    },
    {
        "estacao": "São Caetano do Sul",
        "municipio": "São Caetano do Sul",
        "latitude": -23.6181,
        "longitude": -46.5575,
        "altitude_m": 744,
        "pm25_medio": 19.5,
        "pm10_medio": 36.2,
        "no2_medio": 42.1,
        "dias_ultrapassagem_oms": 64,
        "perfil": "Urbano Denso / Eixo Mauá"
    },
    {
        "estacao": "Diadema",
        "municipio": "Diadema",
        "latitude": -23.6872,
        "longitude": -46.6125,
        "altitude_m": 765,
        "pm25_medio": 18.9,
        "pm10_medio": 35.1,
        "no2_medio": 37.8,
        "dias_ultrapassagem_oms": 61,
        "perfil": "Industrial / Automotivo"
    },
    {
        "estacao": "Osasco",
        "municipio": "Osasco",
        "latitude": -23.5267,
        "longitude": -46.7919,
        "altitude_m": 750,
        "pm25_medio": 20.4,
        "pm10_medio": 38.0,
        "no2_medio": 43.6,
        "dias_ultrapassagem_oms": 68,
        "perfil": "Urbano / Eixo Castelo Branco"
    },
    {
        "estacao": "Guarulhos - Paço Municipal",
        "municipio": "Guarulhos",
        "latitude": -23.4633,
        "longitude": -46.5283,
        "altitude_m": 760,
        "pm25_medio": 19.8,
        "pm10_medio": 37.4,
        "no2_medio": 41.9,
        "dias_ultrapassagem_oms": 65,
        "perfil": "Urbano / Rodovias Dutra-Airpt"
    },
    {
        "estacao": "Taboão da Serra",
        "municipio": "Taboão da Serra",
        "latitude": -23.6067,
        "longitude": -46.7583,
        "altitude_m": 740,
        "pm25_medio": 17.9,
        "pm10_medio": 33.5,
        "no2_medio": 35.7,
        "dias_ultrapassagem_oms": 54,
        "perfil": "Eixo Rodoviário Régis Bittencourt"
    }
]

def classificar_qualidade(pm25):
    """Classificação baseada nos padrões CONAMA 506/2024 e OMS."""
    if pm25 <= 15.0:
        return "Boa (Dentro da meta OMS 24h)"
    elif pm25 <= 25.0:
        return "Moderada (Meta Intermediária 4)"
    elif pm25 <= 35.0:
        return "Ruim (Alerta para grupos sensíveis)"
    else:
        return "Muito Ruim (Risco à saúde pública)"

def processar_dados():
    print("-> Iniciando processamento de dados das estações CETESB...")
    df = pd.DataFrame(ESTACOES_CETESB)
    
    # Adicionar classificação de qualidade do ar
    df["qualidade_ar"] = df["pm25_medio"].apply(classificar_qualidade)
    
    # Salvar CSV tabular
    csv_path = "cetesb_estacoes_qualidade_ar.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[OK] Arquivo CSV exportado com sucesso: {csv_path}")
    
    # Criar GeoJSON padrão para abrir no QGIS
    geojson_features = []
    for _, row in df.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row["longitude"], row["latitude"]]
            },
            "properties": {
                "estacao": row["estacao"],
                "municipio": row["municipio"],
                "pm25_medio_ug_m3": row["pm25_medio"],
                "pm10_medio_ug_m3": row["pm10_medio"],
                "no2_medio_ug_m3": row["no2_medio"],
                "dias_ultrapassagem_oms": row["dias_ultrapassagem_oms"],
                "altitude_m": row["altitude_m"],
                "perfil": row["perfil"],
                "qualidade_ar": row["qualidade_ar"]
            }
        }
        geojson_features.append(feature)
        
    geojson_data = {
        "type": "FeatureCollection",
        "name": "cetesb_qualidade_ar_rmspo",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": geojson_features
    }
    
    geojson_path = "cetesb_estacoes_qualidade_ar.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Camada Geoespacial GeoJSON gerada para o QGIS: {geojson_path}")
    
    return df

def gerar_mapa_tematico(df):
    print("-> Gerando visualizacao cartografica tematica...")
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(12, 10), dpi=300)
    
    # Configurar limites da Grande São Paulo
    lon_min, lon_max = -46.85, -46.40
    lat_min, lat_max = -23.82, -23.42
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    
    # Fundo estilizado simulando malha territorial
    ax.set_facecolor("#f8f9fa")
    
    # Scatter plot com gradiente de cor por concentração de PM2.5
    scatter = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["pm25_medio"],
        cmap="YlOrRd",
        s=df["pm25_medio"] * 18,  # Tamanho proporcional à concentração
        alpha=0.88,
        edgecolors="#2b2b2b",
        linewidths=1.5,
        zorder=5
    )
    
    # Anotações dos nomes das estações
    for _, row in df.iterrows():
        ax.annotate(
            f"{row['estacao']}\n({row['pm25_medio']:.1f} ug/m3)",
            (row["longitude"], row["latitude"]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color="#1a1a1a",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#cccccc", alpha=0.85, lw=0.7),
            zorder=6
        )
        
    # Barra de cores
    cbar = plt.colorbar(scatter, ax=ax, orientation="vertical", pad=0.02, shrink=0.75)
    cbar.set_label("PM2.5 sintetico (ug/m3)", fontsize=11, fontweight="bold", labelpad=10)
    cbar.ax.axhline(15.0, color="green", linestyle="--", linewidth=1.5, label="Valor-guia OMS 24 h (15 ug/m3)")
    
    # Títulos e Metadados Científicos
    plt.title(
        "Distribuicao Espacial de Material Particulado Fino ($PM_{2.5}$) na RMSP\n"
        "Valores sinteticos sobre posicoes de estacoes CETESB",
        fontsize=14,
        fontweight="bold",
        pad=15,
        color="#0d1b2a"
    )
    ax.set_xlabel("Longitude (WGS84)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Latitude (WGS84)", fontsize=11, fontweight="bold")
    
    # Legenda explicativa
    legend_elements = [
        Patch(facecolor="#fed976", edgecolor="#2b2b2b", label="12 - 17 ug/m3 (Niveis Baixos a Moderados)"),
        Patch(facecolor="#fd8d3c", edgecolor="#2b2b2b", label="18 - 20 ug/m3 (Moderado / Alerta OMS)"),
        Patch(facecolor="#bd0026", edgecolor="#2b2b2b", label="> 20 ug/m3 (Eixos Industriais / Trafego Critico)"),
        plt.Line2D([0], [0], color="green", lw=1.5, linestyle="--", label="Valor-guia OMS 24 h (15 ug/m3)")
    ]
    ax.legend(handles=legend_elements, loc="lower left", frameon=True, framealpha=0.92, facecolor="white", fontsize=9)
    
    # Nota de rodapé técnica
    plt.figtext(
        0.13, 0.02,
        "Fonte: Dados de estacoes automaticas CETESB compilados para integracao espacial (Projeto NSEE/Maua - FSP/USP).\n"
        "Elaborado por: Lucas Fischer Paez | Pipeline automatizado Python + Camada QGIS.",
        fontsize=8, color="#555555"
    )
    
    output_png = "mapa_qualidade_ar_sp.png"
    plt.tight_layout()
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Mapa tematico de alta resolucao salvo: {output_png}")

if __name__ == "__main__":
    df_cetesb = processar_dados()
    gerar_mapa_tematico(df_cetesb)
    print("\n[OK] Pipeline concluido com sucesso!")
