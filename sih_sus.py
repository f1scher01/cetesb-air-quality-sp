"""
Internações hospitalares do SUS (SIH/SUS) de residentes da RMSP, agregadas por município.

Fonte: arquivos RDSP<AAMM>.dbc do FTP público do DATASUS (AIH reduzida, estado de São
Paulo). Cada arquivo reúne as AIH aprovadas numa competência, isto é, no mês de
processamento, e não no mês em que a internação ocorreu.

Fluxo:
    1. baixa as competências pedidas;
    2. descomprime o DBC (DBF compactado com PKWare DCL implode) com datasus-dbc;
    3. lê o DBF por mapeamento de memória, com o layout de largura fixa do cabeçalho,
       extraindo só as colunas usadas;
    4. mantém AIH do tipo 1 (principal) de residentes nos 39 municípios da RMSP;
    5. classifica o diagnóstico principal pela CID-10 e a idade em faixas;
    6. agrega por município, competência, mês de internação, grupo e faixa etária.

Privacidade: os arquivos brutos trazem CEP e data de nascimento. Eles ficam em
dados/brutos/sih (fora do git) e o DBF descomprimido é apagado após a leitura. Só a
tabela agregada é gravada no repositório.

Uso:
    python sih_sus.py 2507 2606          # competência inicial e final, formato AAMM

Dependência extra (MIT), instalável no Python do QGIS:
    python -m pip install --user datasus-dbc

Autor: Lucas Fischer Paez
"""

import struct
import sys
import urllib.request

import numpy as np
import pandas as pd

import config
from limites_ibge import municipios_rmsp

FTP_SIH = "ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados"
DIR_SIH = config.DIR_BRUTOS / "sih"
COLUNAS = ["IDENT", "MUNIC_RES", "DT_INTER", "DIAG_PRINC", "COD_IDADE", "IDADE", "MORTE", "DIAS_PERM", "VAL_TOT"]
SAIDA = config.DIR_PROCESSADOS / "sih_rmsp_internacoes.csv"


def competencias(inicio, fim):
    """Lista AAMM de inicio a fim, inclusive."""
    datas = pd.period_range(pd.Period(f"20{inicio[:2]}-{inicio[2:]}", "M"), pd.Period(f"20{fim[:2]}-{fim[2:]}", "M"), freq="M")
    return [f"{p.year % 100:02d}{p.month:02d}" for p in datas]


def baixar(aamm):
    DIR_SIH.mkdir(parents=True, exist_ok=True)
    destino = DIR_SIH / f"RDSP{aamm}.dbc"
    if not destino.exists() or destino.stat().st_size == 0:
        urllib.request.urlretrieve(f"{FTP_SIH}/{destino.name}", destino)
    return destino


def ler_dbf(caminho, colunas):
    """Lê colunas de um DBF (dBase III) sem biblioteca externa.

    O cabeçalho informa número de registros, tamanho do cabeçalho e tamanho do
    registro; cada descritor de campo tem 32 bytes com nome e largura. Como os
    registros têm largura fixa, o arquivo inteiro vira um array estruturado do NumPy.
    """
    with open(caminho, "rb") as f:
        n_registros, tam_cabecalho, tam_registro = struct.unpack("<IHH", f.read(32)[4:12])
        campos = []
        while True:
            descritor = f.read(32)
            if descritor[0] == 0x0D:
                break
            campos.append((descritor[:11].split(b"\0")[0].decode("ascii"), descritor[16]))

    tipo = np.dtype([("_apagado", "S1")] + [(nome, f"S{largura}") for nome, largura in campos])
    if tipo.itemsize != tam_registro:
        raise ValueError(f"Layout inconsistente: {tipo.itemsize} bytes somados, {tam_registro} no cabeçalho")

    registros = np.memmap(caminho, dtype=tipo, mode="r", offset=tam_cabecalho, shape=(n_registros,))
    validos = registros["_apagado"] != b"*"
    tabela = pd.DataFrame({
        c: pd.Series(np.char.decode(registros[c][validos], "latin-1")).str.strip() for c in colunas
    })
    del registros
    return tabela


def classificar(tabela):
    """Acrescenta capítulo e subgrupo da CID-10 e faixa etária."""
    cid = tabela["DIAG_PRINC"]
    letra = cid.str[0]
    numero = pd.to_numeric(cid.str[1:3], errors="coerce")

    tabela["capitulo"] = np.select([letra == "J", letra == "I"],
                                   ["respiratorio (J00-J99)", "circulatorio (I00-I99)"], default="")
    tabela["subgrupo"] = np.select(
        [(letra == "J") & numero.between(12, 18), (letra == "J") & numero.between(40, 47), letra == "J"],
        ["pneumonia (J12-J18)", "DPOC e asma (J40-J47)", "outras respiratorias"],
        default=tabela["capitulo"],
    )

    # COD_IDADE: 2 = dias, 3 = meses, 4 = anos, 5 = anos acima de 100.
    idade = pd.to_numeric(tabela["IDADE"], errors="coerce")
    anos = np.select([tabela["COD_IDADE"].isin(["1", "2", "3"]), tabela["COD_IDADE"] == "4", tabela["COD_IDADE"] == "5"],
                     [0, idade, 100 + idade], default=np.nan)
    tabela["faixa_etaria"] = pd.cut(anos, bins=[-1, 4, 64, 200], labels=["0-4", "5-64", "65+"]).astype(str)
    return tabela


def processar(aamm, codigos_rmsp):
    dbc = baixar(aamm)
    dbf = dbc.with_suffix(".dbf")
    import datasus_dbc
    datasus_dbc.decompress(str(dbc), str(dbf))
    try:
        tabela = ler_dbf(dbf, COLUNAS)
    finally:
        dbf.unlink(missing_ok=True)

    total = len(tabela)
    tabela = tabela[(tabela["IDENT"] == "1") & tabela["MUNIC_RES"].isin(codigos_rmsp)]
    tabela = classificar(tabela)
    tabela = tabela[tabela["capitulo"] != ""]

    tabela["competencia"] = f"20{aamm[:2]}-{aamm[2:]}"
    tabela["mes_internacao"] = tabela["DT_INTER"].str[:4] + "-" + tabela["DT_INTER"].str[4:6]
    tabela["obito"] = (tabela["MORTE"] == "1").astype(int)
    tabela["dias"] = pd.to_numeric(tabela["DIAS_PERM"], errors="coerce").fillna(0)
    tabela["valor"] = pd.to_numeric(tabela["VAL_TOT"], errors="coerce").fillna(0.0)

    agregado = (tabela.groupby(["MUNIC_RES", "competencia", "mes_internacao", "capitulo", "subgrupo", "faixa_etaria"])
                      .agg(internacoes=("obito", "size"), obitos=("obito", "sum"),
                           dias_permanencia=("dias", "sum"), valor_total_rs=("valor", "sum"))
                      .reset_index()
                      .rename(columns={"MUNIC_RES": "cod_ibge6"}))
    print(f"RDSP{aamm}: {total:7d} AIH no estado, {int(agregado['internacoes'].sum()):6d} "
          f"respiratórias ou circulatórias de residentes da RMSP")
    return agregado


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    municipios = municipios_rmsp()
    codigos = {codigo[:6] for codigo in municipios}   # SIH usa o código IBGE sem o dígito verificador

    partes = [processar(aamm, codigos) for aamm in competencias(sys.argv[1], sys.argv[2])]
    resultado = pd.concat(partes, ignore_index=True)
    nomes = {codigo[:6]: nome for codigo, nome in municipios.items()}
    resultado.insert(1, "municipio", resultado["cod_ibge6"].map(nomes))
    resultado["valor_total_rs"] = resultado["valor_total_rs"].round(2)
    resultado.to_csv(SAIDA, index=False, encoding="utf-8")
    print(f"{int(resultado['internacoes'].sum())} internações agregadas em {SAIDA.name}")


if __name__ == "__main__":
    main()
