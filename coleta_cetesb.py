"""
Coleta das últimas 48 horas da rede automática da CETESB.

Fonte: o serviço ArcGIS REST público que alimenta o mapa do QUALAR. Cada camada
traz, por estação, 48 valores horários de índice (M1..M48) e os respectivos
instantes (TM1..TM48, epoch em ms, UTC), mais a geometria em SIRGAS 2000.

Como a janela é móvel, cada execução grava um snapshot bruto com data e acrescenta
as observações a uma série longa sem duplicar horas já coletadas. Rodar uma vez
por dia (Agendador de Tarefas do Windows) constrói o histórico.

Uso:
    python coleta_cetesb.py

Saídas:
    dados/brutos/cetesb_<camada>_<AAAAMMDDTHHMMZ>.json   resposta original do serviço
    dados/processados/cetesb_serie_horaria.csv           série longa acumulada
    dados/processados/cetesb_estacoes.geojson            estações com MP2,5 (EPSG:4674)

Autor: Lucas Fischer Paez
"""

import json
from datetime import datetime, timezone

import pandas as pd
import requests

import config


def consultar_camada(id_camada):
    """Consulta todas as feições de uma camada do MapServer."""
    url = f"{config.CETESB_MAPSERVER}/{id_camada}/query"
    parametros = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4674", "f": "json"}
    resposta = requests.get(url, params=parametros, timeout=60)
    resposta.raise_for_status()
    dados = resposta.json()
    if "error" in dados:
        raise RuntimeError(f"Camada {id_camada}: {dados['error']}")
    return dados


def indice_para_concentracao(indice, faixas=config.FAIXAS_INDICE_MP25):
    """Inverte a função linear segmentada do índice (adimensional -> µg/m³).

    O índice publicado é inteiro, então a inversão tem incerteza de meio passo:
    ±0,19 µg/m³ na faixa N1 (15/40 por unidade de índice) e ±0,44 µg/m³ na N2.
    """
    if indice is None or pd.isna(indice):
        return None
    for i_ini, i_fim, c_ini, c_fim in faixas:
        if i_ini <= indice <= i_fim:
            return round(c_ini + (indice - i_ini) * (c_fim - c_ini) / (i_fim - i_ini), 2)
    return None


def para_formato_longo(dados, poluente):
    """Converte M1..M48 / TM1..TM48 em linhas (estação, poluente, instante, índice)."""
    linhas = []
    for feicao in dados["features"]:
        atributos, geometria = feicao["attributes"], feicao.get("geometry") or {}
        for n in range(1, 49):
            instante = atributos.get(f"TM{n}")
            if instante is None:
                continue
            linhas.append({
                "estacao": atributos["STATNM"],
                "poluente": poluente,
                "datahora_utc": datetime.fromtimestamp(instante / 1000, tz=timezone.utc),
                "indice": atributos.get(f"M{n}"),
                "lon": geometria.get("x"),
                "lat": geometria.get("y"),
            })
    tabela = pd.DataFrame(linhas)
    if poluente == "MP2.5":
        tabela["conc_ug_m3_estimada"] = tabela["indice"].apply(indice_para_concentracao)
    return tabela


def acumular(nova, caminho):
    """Acrescenta à série existente, mantendo a última leitura de cada (estação, poluente, hora)."""
    if caminho.exists():
        antiga = pd.read_csv(caminho, parse_dates=["datahora_utc"])
        nova = pd.concat([antiga, nova], ignore_index=True)
    nova = (nova.drop_duplicates(subset=["estacao", "poluente", "datahora_utc"], keep="last")
                .sort_values(["poluente", "estacao", "datahora_utc"]))
    nova.to_csv(caminho, index=False, encoding="utf-8")
    return nova


def exportar_estacoes(dados_mp25, caminho):
    """Grava as estações que medem MP2,5 como GeoJSON para o QGIS."""
    feicoes = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [f["geometry"]["x"], f["geometry"]["y"]]},
        "properties": {"estacao": f["attributes"]["STATNM"]},
    } for f in dados_mp25["features"] if f.get("geometry")]
    colecao = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
        "features": feicoes,
    }
    caminho.write_text(json.dumps(colecao, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(feicoes)


def main():
    config.DIR_BRUTOS.mkdir(parents=True, exist_ok=True)
    config.DIR_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")

    tabelas = []
    for poluente in ("MP2.5", "MP10"):
        dados = consultar_camada(config.CETESB_CAMADAS[poluente])
        nome = poluente.replace(".", "")
        (config.DIR_BRUTOS / f"cetesb_{nome}_{carimbo}.json").write_text(
            json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tabela = para_formato_longo(dados, poluente)
        tabelas.append(tabela)
        print(f"{poluente:6s} {tabela['estacao'].nunique():3d} estações, "
              f"{tabela['indice'].notna().sum():5d} valores horários, "
              f"{tabela['datahora_utc'].min():%d/%m %H:%M} a {tabela['datahora_utc'].max():%d/%m %H:%M} UTC")
        if poluente == "MP2.5":
            n = exportar_estacoes(dados, config.DIR_PROCESSADOS / "cetesb_estacoes.geojson")
            print(f"       {n} estações exportadas para GeoJSON")

    serie = acumular(pd.concat(tabelas, ignore_index=True),
                     config.DIR_PROCESSADOS / "cetesb_serie_horaria.csv")
    print(f"Série acumulada: {len(serie)} linhas")


if __name__ == "__main__":
    main()
