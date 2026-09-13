"""
Motor Avancado de Analise Geoespacial e Modelagem Epidemiologica
Projeto: Integracao Satelital MAIA-NASA, Rede CETESB e Morbidade Hospitalar (SIH/SUS)
Autor: Lucas Fischer Paez
"""

import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.gridspec as gridspec

# 1. ESTACOES CETESB COM CARACTERIZACAO FISICO-QUIMICA (ESPECIACAO MAIA)
# LEGADO SINTETICO: concentracoes escritas a mao, sem origem em medicao.
ESTACOES_EXPANDIDAS = [
    {"estacao": "Pinheiros", "municipio": "São Paulo", "lat": -23.5614, "lon": -46.7020, "pm25": 18.4, "pm10": 33.2, "no2": 38.5, "perfil": "Urbano / Trafego"},
    {"estacao": "Cerqueira César", "municipio": "São Paulo", "lat": -23.5535, "lon": -46.6727, "pm25": 20.1, "pm10": 36.8, "no2": 44.2, "perfil": "Corredor Central"},
    {"estacao": "Congonhas", "municipio": "São Paulo", "lat": -23.6163, "lon": -46.6635, "pm25": 22.8, "pm10": 41.5, "no2": 49.0, "perfil": "Aeroportuario / Eixo Sul"},
    {"estacao": "Parque D. Pedro II", "municipio": "São Paulo", "lat": -23.5448, "lon": -46.6277, "pm25": 21.5, "pm10": 39.4, "no2": 46.8, "perfil": "Centro Historico"},
    {"estacao": "Santana", "municipio": "São Paulo", "lat": -23.5050, "lon": -46.6288, "pm25": 17.6, "pm10": 32.0, "no2": 36.4, "perfil": "Zona Norte"},
    {"estacao": "Mooca", "municipio": "São Paulo", "lat": -23.5500, "lon": -46.5986, "pm25": 19.3, "pm10": 35.7, "no2": 41.0, "perfil": "Misto / Industrial"},
    {"estacao": "Grajaú - Parelheiros", "municipio": "São Paulo", "lat": -23.7767, "lon": -46.6953, "pm25": 12.3, "pm10": 24.1, "no2": 21.5, "perfil": "Mananciais / Fundo"},
    {"estacao": "Interlagos", "municipio": "São Paulo", "lat": -23.6806, "lon": -46.6753, "pm25": 15.8, "pm10": 29.6, "no2": 30.2, "perfil": "Represa / Residencial"},
    {"estacao": "Santo Amaro", "municipio": "São Paulo", "lat": -23.6525, "lon": -46.7094, "pm25": 18.0, "pm10": 34.0, "no2": 39.5, "perfil": "Comercial / Sul"},
    {"estacao": "Itaquera", "municipio": "São Paulo", "lat": -23.5800, "lon": -46.4580, "pm25": 16.9, "pm10": 31.8, "no2": 33.1, "perfil": "Zona Leste"},
    {"estacao": "Mauá", "municipio": "Mauá", "lat": -23.6683, "lon": -46.4614, "pm25": 20.7, "pm10": 38.5, "no2": 43.0, "perfil": "Polo Petroquimico"},
    {"estacao": "Santo André - Capuava", "municipio": "Santo André", "lat": -23.6450, "lon": -46.4950, "pm25": 21.2, "pm10": 39.1, "no2": 45.2, "perfil": "Industrial ABC"},
    {"estacao": "São Caetano do Sul", "municipio": "São Caetano do Sul", "lat": -23.6181, "lon": -46.5575, "pm25": 19.5, "pm10": 36.2, "no2": 42.1, "perfil": "Urbano Denso"},
    {"estacao": "Diadema", "municipio": "Diadema", "lat": -23.6872, "lon": -46.6125, "pm25": 18.9, "pm10": 35.1, "no2": 37.8, "perfil": "Industrial Sul"},
    {"estacao": "Osasco", "municipio": "Osasco", "lat": -23.5267, "lon": -46.7919, "pm25": 20.4, "pm10": 38.0, "no2": 43.6, "perfil": "Eixo Oeste"},
    {"estacao": "Guarulhos", "municipio": "Guarulhos", "lat": -23.4633, "lon": -46.5283, "pm25": 19.8, "pm10": 37.4, "no2": 41.9, "perfil": "Rodoviario / Aeroporto"},
    {"estacao": "Taboão da Serra", "municipio": "Taboão da Serra", "lat": -23.6067, "lon": -46.7583, "pm25": 17.9, "pm10": 33.5, "no2": 35.7, "perfil": "Eixo Regis"}
]

# 2. DISTRITOS REPRESENTATIVOS PARA AVALIACAO EPIDEMIOLOGICA (SIH/SUS)
DISTRITOS_SP = [
    {"distrito": "Sé / República", "lat": -23.5489, "lon": -46.6388, "populacao": 150000, "base_internacoes_cardio": 1420, "base_internacoes_resp": 1950},
    {"distrito": "Pinheiros", "lat": -23.5670, "lon": -46.6930, "populacao": 290000, "base_internacoes_cardio": 2100, "base_internacoes_resp": 2450},
    {"distrito": "Mooca", "lat": -23.5600, "lon": -46.6000, "populacao": 320000, "base_internacoes_cardio": 2800, "base_internacoes_resp": 3100},
    {"distrito": "Santo Amaro", "lat": -23.6500, "lon": -46.7050, "populacao": 240000, "base_internacoes_cardio": 1950, "base_internacoes_resp": 2300},
    {"distrito": "Santana / Tucuruvi", "lat": -23.4950, "lon": -46.6200, "populacao": 330000, "base_internacoes_cardio": 2600, "base_internacoes_resp": 3250},
    {"distrito": "Itaquera", "lat": -23.5400, "lon": -46.4600, "populacao": 520000, "base_internacoes_cardio": 3800, "base_internacoes_resp": 5400},
    {"distrito": "Lapa", "lat": -23.5200, "lon": -46.7000, "populacao": 310000, "base_internacoes_cardio": 2400, "base_internacoes_resp": 2700},
    {"distrito": "São Mateus", "lat": -23.6000, "lon": -46.4700, "populacao": 430000, "base_internacoes_cardio": 3100, "base_internacoes_resp": 4600},
    {"distrito": "Campo Limpo", "lat": -23.6300, "lon": -46.7600, "populacao": 390000, "base_internacoes_cardio": 2750, "base_internacoes_resp": 3900},
    {"distrito": "Parelheiros", "lat": -23.7700, "lon": -46.7100, "populacao": 160000, "base_internacoes_cardio": 950, "base_internacoes_resp": 1500}
]

def calcular_especiacao_maia(pm25):
    """
    Fracionamento por PERCENTUAIS FIXOS escolhidos a mao (nao e especiacao medida).
    As especies listadas sao as que a missao MAIA pretende estimar; os percentuais nao vem dela:
    - Sulfato (SO4): ~18% (processos de oxidacao atmosferica de enxofre)
    - Nitrato (NO3): ~16% (emissoes veiculares e formacao fotoquimica)
    - Carbono Organico (OC): ~34% (combustao primária e aerossol secundario)
    - Carbono Elementar / Black Carbon (EC): ~14% (queima a diesel)
    - Poeira Mineral / Solo (Dust): ~18% (ressuspensao mecânica)
    """
    return {
        "sulfato_ug_m3": round(pm25 * 0.18, 2),
        "nitrato_ug_m3": round(pm25 * 0.16, 2),
        "carbono_organico_ug_m3": round(pm25 * 0.34, 2),
        "carbono_elementar_ug_m3": round(pm25 * 0.14, 2),
        "poeira_mineral_ug_m3": round(pm25 * 0.18, 2)
    }

def interpolacao_idw(x_obs, y_obs, z_obs, x_grid, y_grid, power=2):
    """
    Interpolacao espacial por Inverso da Distancia Ponderada (IDW).
    Produz a superficie continua de concentracao de poluentes sobre a RMSP.
    """
    n_points = len(x_obs)
    shape = x_grid.shape
    z_interp = np.zeros(shape)
    
    for i in range(shape[0]):
        for j in range(shape[1]):
            gx, gy = x_grid[i, j], y_grid[i, j]
            dists = np.sqrt((x_obs - gx)**2 + (y_obs - gy)**2)
            
            # Se coincide com uma estacao de medicao
            if np.any(dists < 1e-6):
                idx = np.argmin(dists)
                z_interp[i, j] = z_obs[idx]
            else:
                weights = 1.0 / (dists ** power)
                z_interp[i, j] = np.sum(weights * z_obs) / np.sum(weights)
                
    return z_interp

def estimar_risco_saude_publica(pm25_exposicao, base_cardio, base_resp):
    """
    Modelagem epidemiologica segundo Funcoes Concentracao-Resposta (OMS):
    - Limiar de referencia (OMS 2021): C0 = 5.0 ug/m3
    - Beta Cardio (CID-10 I00-I99): beta = 0.008 por ug/m3 (aumento de ~8% a cada 10 ug/m3)
    - Beta Resp (CID-10 J00-J99): beta = 0.011 por ug/m3 (aumento de ~11% a cada 10 ug/m3)
    """
    delta_c = max(0.0, pm25_exposicao - 5.0)
    
    rr_cardio = np.exp(0.008 * delta_c)
    rr_resp = np.exp(0.011 * delta_c)
    
    # Fracao Atribuivel Populacional: PAF = (RR - 1) / RR
    paf_cardio = (rr_cardio - 1.0) / rr_cardio
    paf_resp = (rr_resp - 1.0) / rr_resp
    
    casos_cardio_atribuiveis = int(round(base_cardio * paf_cardio))
    casos_resp_atribuiveis = int(round(base_resp * paf_resp))
    
    return {
        "pm25_exposicao": round(pm25_exposicao, 2),
        "rr_cardiovascular": round(rr_cardio, 4),
        "rr_respiratorio": round(rr_resp, 4),
        "internacoes_cardio_atribuiveis": casos_cardio_atribuiveis,
        "internacoes_resp_atribuiveis": casos_resp_atribuiveis,
        "total_internacoes_atribuiveis": casos_cardio_atribuiveis + casos_resp_atribuiveis
    }

def executar_pipeline_completo():
    print("===============================================================")
    print("  INICIANDO MOTOR GEOESPACIAL MAIA-NASA / CETESB / SIH-SUS")
    print("===============================================================")
    
    # 1. Expandir base com composicao quimica
    estacoes_processadas = []
    for est in ESTACOES_EXPANDIDAS:
        espec = calcular_especiacao_maia(est["pm25"])
        item = {**est, **espec}
        estacoes_processadas.append(item)
        
    df_estacoes = pd.DataFrame(estacoes_processadas)
    df_estacoes.to_csv("cetesb_estacoes_especiacao_maia.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] Base de dados de especiacao exportada: cetesb_estacoes_especiacao_maia.csv")
    
    # 2. Gerar grade espacial contínua (IDW)
    x_obs = df_estacoes["lon"].values
    y_obs = df_estacoes["lat"].values
    z_obs = df_estacoes["pm25"].values
    
    grid_lons = np.linspace(-46.85, -46.40, 60)
    grid_lats = np.linspace(-23.82, -23.42, 60)
    glon, glat = np.meshgrid(grid_lons, grid_lats)
    
    print("-> Executando interpolacao geoespacial (IDW quadratico)...")
    pm25_superficie = interpolacao_idw(x_obs, y_obs, z_obs, glon, glat, power=2)
    print("[OK] Superficie IDW interpolada: grade 60x60 (~770 m em longitude).")
    
    # 3. Cruzamento com distritos e calculo epidemiologico
    distritos_analise = []
    for d in DISTRITOS_SP:
        # Calcular concentracao interpolada no centroide do distrito
        dists = np.sqrt((x_obs - d["lon"])**2 + (y_obs - d["lat"])**2)
        pesos = 1.0 / (dists**2)
        pm_est = np.sum(pesos * z_obs) / np.sum(pesos)
        
        saude = estimar_risco_saude_publica(pm_est, d["base_internacoes_cardio"], d["base_internacoes_resp"])
        linha = {
            "distrito": d["distrito"],
            "latitude": d["lat"],
            "longitude": d["lon"],
            "populacao": d["populacao"],
            **saude
        }
        distritos_analise.append(linha)
        
    df_distritos = pd.DataFrame(distritos_analise)
    df_distritos.to_csv("exposicao_e_saude_distritos_sp.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] Relatorio epidemiologico SIH/SUS exportado: exposicao_e_saude_distritos_sp.csv")
    
    # 4. Renderizacao do Painel Cientifico de Alta Densidade (PNG 300 DPI)
    print("-> Gerando composicao cartografica de alta definicao...")
    fig = plt.figure(figsize=(19, 8.5), dpi=300)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.15, 0.85], wspace=0.36)
    
    # PAINEL 1: Mapa Cartografico com Contornos de Poluicao e Estacoes
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor("#f8fafc")
    ax1.set_xlim(-46.85, -46.38)
    ax1.set_ylim(-23.82, -23.42)
    
    contour = ax1.contourf(
        glon, glat, pm25_superficie,
        levels=np.linspace(12.0, 23.5, 24),
        cmap="YlOrRd",
        alpha=0.85
    )
    cbar = plt.colorbar(contour, ax=ax1, orientation="horizontal", pad=0.10, shrink=0.85)
    cbar.set_label("Concentração Estimada de PM₂.₅ (µg/m³) — Superfície Contínua", fontsize=9.5, fontweight="bold")
    
    # Plotar estacoes CETESB
    ax1.scatter(
        df_estacoes["lon"], df_estacoes["lat"],
        c="#1e3a8a", s=65, edgecolors="white", linewidths=1.5, zorder=5, label="Estação CETESB"
    )
    
    # Dicionario de offsets direcionados para evitar qualquer sobreposicao de rotulos
    rotulo_offsets = {
        "Sé / República": (0, 9),
        "Pinheiros": (-22, -14),
        "Mooca": (22, -14),
        "Santo Amaro": (22, -14),
        "Santana / Tucuruvi": (0, 9),
        "Itaquera": (0, 9),
        "Lapa": (0, 9),
        "São Mateus": (0, -18),
        "Campo Limpo": (-26, 9),
        "Parelheiros": (0, 9)
    }

    # Plotar distritos avaliados com rotulos
    for _, row in df_distritos.iterrows():
        ax1.plot(row["longitude"], row["latitude"], marker="s", color="#0f172a", markersize=6, zorder=6)
        dist_name = row["distrito"]
        offset = rotulo_offsets.get(dist_name, (0, 9))
        ax1.annotate(
            f"{dist_name}\n(+{row['total_internacoes_atribuiveis']} int.)",
            (row["longitude"], row["latitude"]),
            xytext=offset, textcoords="offset points",
            ha="center", fontsize=7.2, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#94a3b8", alpha=0.92, lw=0.7),
            zorder=7
        )
        
    ax1.set_title("A) IDW sobre PM₂.₅ sintético e saída do modelo C-R", fontsize=11.5, fontweight="bold", pad=12)
    ax1.set_xlabel("Longitude (WGS84)", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Latitude (WGS84)", fontsize=10, fontweight="bold")
    ax1.legend(loc="lower left", fontsize=9, framealpha=0.92)
    
    # PAINEL 2: Especiacao Quimica de Aerossois (Alvo Central MAIA-NASA)
    ax2 = fig.add_subplot(gs[1])
    amostras_espec = df_estacoes[df_estacoes["estacao"].isin(["Congonhas", "Mauá", "Parque D. Pedro II", "Cerqueira César", "Grajaú - Parelheiros"])].copy()
    
    fracoes = ["sulfato_ug_m3", "nitrato_ug_m3", "carbono_organico_ug_m3", "carbono_elementar_ug_m3", "poeira_mineral_ug_m3"]
    labels_fracoes = ["Sulfato (SO₄²⁻)", "Nitrato (NO₃⁻)", "Carbono Orgânico (OC)", "Black Carbon (EC)", "Poeira Mineral"]
    cores = ["#38bdf8", "#818cf8", "#fbbf24", "#334155", "#a3e635"]
    
    y_pos = np.arange(len(amostras_espec))
    left = np.zeros(len(amostras_espec))
    
    for i, frac in enumerate(fracoes):
        ax2.barh(y_pos, amostras_espec[frac], left=left, color=cores[i], label=labels_fracoes[i], edgecolor="#1e293b", height=0.55)
        left += amostras_espec[frac].values
        
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(amostras_espec["estacao"], fontsize=9.5, fontweight="bold")
    ax2.tick_params(axis="y", pad=8)
    ax2.invert_yaxis()
    ax2.set_xlabel("Concentração de PM₂.₅ por Componente Químico (µg/m³)", fontsize=10, fontweight="bold")
    ax2.set_title("B) Fracionamento por percentual fixo (sintético)", fontsize=11.5, fontweight="bold", pad=12)
    ax2.legend(loc="lower right", fontsize=8.5, framealpha=0.95)
    ax2.grid(axis="x", linestyle="--", alpha=0.6)
    
    output_png = "mapa_analise_integrada_sp.png"
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Painel de analise integrada salvo: {output_png}")
    
    # 5. Gerar script de automação QGIS (Python Console)
    script_qgis = """# Script de Automação para o Console Python do QGIS
# Carrega a camada GeoJSON sintetica no projeto aberto (sem simbologia)
import os
from qgis.core import QgsVectorLayer, QgsProject

geojson_path = os.path.abspath("cetesb_estacoes_qualidade_ar.geojson")
layer = QgsVectorLayer(geojson_path, "Estacoes CETESB - Qualidade do Ar", "ogr")

if not layer.isValid():
    print("Erro ao carregar a camada GeoJSON!")
else:
    QgsProject.instance().addMapLayer(layer)
    print("Camada CETESB carregada com sucesso no QGIS!")
"""
    with open("qgis_style_loader.py", "w", encoding="utf-8") as f:
        f.write(script_qgis)
    print(f"[OK] Script de console QGIS gerado: qgis_style_loader.py")
    
    print("\n===============================================================")
    print("  PIPELINE AVANCADO EXECUTADO COM SUCESSO!")
    print("===============================================================")

if __name__ == "__main__":
    executar_pipeline_completo()
