"""
Parâmetros compartilhados pelo pipeline: domínio espacial, caminhos e fontes.

Tudo que é escolha de projeto fica aqui, com a justificativa ao lado, para que
nenhum número mágico apareça espalhado pelos módulos.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_BRUTOS = RAIZ / "dados" / "brutos"        # NetCDF e JSON originais (fora do git)
DIR_PROCESSADOS = RAIZ / "dados" / "processados"
DIR_FIGURAS = RAIZ / "figuras"

# Domínio da Região Metropolitana de São Paulo, em graus (WGS84 / SIRGAS 2000).
# Cobre os 39 municípios da RMSP com folga de ~5 km nas bordas.
BBOX_RMSP = {"lon_min": -47.25, "lon_max": -45.65, "lat_min": -24.10, "lat_max": -23.15}

# Grade de saída do recorte de satélite. O pixel do ABI tem 2 km no nadir; sobre
# São Paulo, a ~40° de ângulo de visada, fica perto de 2,5-3 km. 0,02° (~2,1 km)
# preserva a resolução nativa sem inventar detalhe.
RESOLUCAO_GRAUS = 0.02

# ---------------------------------------------------------------------------
# GOES-19 ABI L2 AOD (NOAA Open Data Dissemination, bucket público na AWS)
# ---------------------------------------------------------------------------
GOES_BUCKET = "https://noaa-goes19.s3.amazonaws.com"
GOES_PRODUTO = "ABI-L2-AODF"   # disco completo; o setor CONUS não cobre o Brasil

# DQF do produto: 0 = alta qualidade, 1 = média, 2 = baixa, 3 = sem retrieval.
# O guia de uso da NOAA recomenda 0-1 para análise quantitativa.
DQF_MAXIMO = 1

# ---------------------------------------------------------------------------
# CETESB — serviço ArcGIS público que alimenta o mapa do QUALAR (sem login)
# ---------------------------------------------------------------------------
CETESB_MAPSERVER = "https://servicos.cetesb.sp.gov.br/arcgis/rest/services/QUALAR/CETESB_QUALAR/MapServer"
CETESB_CAMADAS = {"CO": 0, "MP10": 1, "MP2.5": 2, "NO2": 3, "O3": 4, "SO2": 5}
CETESB_CAMADA_ESTACOES = 6

# O serviço publica o ÍNDICE de qualidade do ar (adimensional), não a concentração.
# Para MP2,5 a inversão índice -> µg/m³ usa a função linear segmentada abaixo.
#
# Evidência para os pontos de quebra: na faixa N1 os índices publicados assumem só
# os valores {3, 5, 8, 11, 13, 16, ...}, exatamente round(40·C/15) com C inteiro em
# µg/m³. Com o limite de 25 µg/m³ da Tabela 2.7 do Relatório de Metodologia da
# CETESB (2025) apareceriam índices como 2, 6 e 10, que nunca ocorrem. Os pontos
# 15/50/75/125 coincidem com a estrutura do IQAr alinhada à Resolução CONAMA 506/2024.
# Tratar como hipótese verificada nos dados, a confirmar contra uma exportação do
# QUALAR em µg/m³.
#   (índice_inicial, índice_final, conc_inicial, conc_final)
FAIXAS_INDICE_MP25 = [
    (0, 40, 0.0, 15.0),
    (40, 80, 15.0, 50.0),
    (80, 120, 50.0, 75.0),
    (120, 200, 75.0, 125.0),
    (200, 400, 125.0, 300.0),
]

# ---------------------------------------------------------------------------
# IBGE — malhas territoriais e composição da RMSP
# ---------------------------------------------------------------------------
IBGE_MALHA_SP = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/35"
    "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=intermediaria"
)
IBGE_MUNICIPIOS_SP = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios"
