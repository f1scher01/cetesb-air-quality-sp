"""
Limites municipais oficiais da Região Metropolitana de São Paulo (IBGE).

Baixa a malha municipal do estado de SP pela API de malhas do IBGE, cruza com a
composição da RMSP (região 04901 na API de localidades) e grava uma camada
GeoJSON com código e nome de cada um dos 39 municípios.

Uso:
    python limites_ibge.py

Saída:
    dados/processados/rmsp_municipios.geojson   (SIRGAS 2000, EPSG:4674)

Autor: Lucas Fischer Paez
"""

import json

import requests

import config

ID_RMSP = "04901"
URL_REGIOES = "https://servicodados.ibge.gov.br/api/v1/localidades/regioes-metropolitanas"


def municipios_rmsp():
    """Dicionário {código IBGE de 7 dígitos: nome} dos municípios da RMSP."""
    regioes = requests.get(URL_REGIOES, timeout=60).json()
    rmsp = next(r for r in regioes if r["id"] == ID_RMSP)
    return {str(m["id"]): m["nome"] for m in rmsp["municipios"]}


def main():
    composicao = municipios_rmsp()
    malha = requests.get(config.IBGE_MALHA_SP, timeout=120).json()

    feicoes = []
    for feicao in malha["features"]:
        codigo = str(feicao["properties"].get("codarea"))
        if codigo in composicao:
            feicao["properties"] = {"cod_ibge": codigo, "nome": composicao[codigo]}
            feicoes.append(feicao)

    faltando = set(composicao) - {f["properties"]["cod_ibge"] for f in feicoes}
    if faltando:
        raise RuntimeError(f"Municípios da RMSP sem geometria na malha: {sorted(faltando)}")

    saida = config.DIR_PROCESSADOS / "rmsp_municipios.geojson"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
        "features": feicoes,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"{len(feicoes)} municípios da RMSP gravados em {saida.name}")


if __name__ == "__main__":
    main()
