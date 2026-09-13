"""
Limites municipais oficiais e população estimada da Região Metropolitana de São Paulo.

Baixa a malha municipal do estado de SP pela API de malhas do IBGE, cruza com a
composição da RMSP (região 04901 na API de localidades), anexa a estimativa
populacional mais recente (SIDRA, tabela 6579) e grava uma camada GeoJSON.

Uso:
    python limites_ibge.py

Saída:
    dados/processados/rmsp_municipios.geojson   (SIRGAS 2000, EPSG:4674)
    propriedades: cod_ibge (inteiro, 7 dígitos), nome, pop_estimada, ano_pop

Autor: Lucas Fischer Paez
"""

import json

import requests

import config

ID_RMSP = "04901"
URL_REGIOES = "https://servicodados.ibge.gov.br/api/v1/localidades/regioes-metropolitanas"
URL_POPULACAO = "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-1/variaveis/9324"


def municipios_rmsp():
    """Dicionário {código IBGE de 7 dígitos: nome} dos municípios da RMSP."""
    regioes = requests.get(URL_REGIOES, timeout=60).json()
    rmsp = next(r for r in regioes if r["id"] == ID_RMSP)
    return {str(m["id"]): m["nome"] for m in rmsp["municipios"]}


def populacao_estimada(codigos):
    """População residente estimada no período mais recente publicado pelo IBGE."""
    resposta = requests.get(URL_POPULACAO, params={"localidades": f"N6[{','.join(codigos)}]"}, timeout=60)
    resposta.raise_for_status()
    series = resposta.json()[0]["resultados"][0]["series"]
    populacao = {}
    for s in series:
        ano, valor = next(iter(s["serie"].items()))
        populacao[s["localidade"]["id"]] = (int(valor), int(ano))
    return populacao


def main():
    composicao = municipios_rmsp()
    populacao = populacao_estimada(sorted(composicao))
    malha = requests.get(config.IBGE_MALHA_SP, timeout=120).json()

    feicoes = []
    for feicao in malha["features"]:
        codigo = str(feicao["properties"].get("codarea"))
        if codigo in composicao:
            pop, ano = populacao[codigo]
            feicao["properties"] = {"cod_ibge": int(codigo), "nome": composicao[codigo],
                                    "pop_estimada": pop, "ano_pop": ano}
            feicoes.append(feicao)

    faltando = set(composicao) - {str(f["properties"]["cod_ibge"]) for f in feicoes}
    if faltando:
        raise RuntimeError(f"Municípios da RMSP sem geometria na malha: {sorted(faltando)}")

    saida = config.DIR_PROCESSADOS / "rmsp_municipios.geojson"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4674"}},
        "features": feicoes,
    }, ensure_ascii=False), encoding="utf-8")
    total = sum(f["properties"]["pop_estimada"] for f in feicoes)
    print(f"{len(feicoes)} municípios da RMSP gravados em {saida.name} "
          f"(população estimada {feicoes[0]['properties']['ano_pop']}: {total:,})".replace(",", "."))


if __name__ == "__main__":
    main()
