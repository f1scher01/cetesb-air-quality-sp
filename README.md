# Integração Geoespacial de Poluição Atmosférica e Saúde Coletiva

### Estudo metodológico com dados sintéticos — Missão MAIA-NASA, rede CETESB e SIH/SUS

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![NumPy](https://img.shields.io/badge/NumPy-IDW%20implementado%20à%20mão-013243?logo=numpy)](https://numpy.org/)
[![Dados](https://img.shields.io/badge/Dados-SINTÉTICOS-critical)](#-aviso-os-dados-deste-repositório-são-sintéticos)
[![Status](https://img.shields.io/badge/Status-Demonstração%20metodológica-blue)](#)

---

## ⚠️ Aviso: os dados deste repositório são sintéticos

**Nenhum dado real da CETESB, da NASA ou do SIH/SUS é utilizado aqui.**

As concentrações das estações (`ESTACOES_EXPANDIDAS`) e as bases de internação por distrito
(`DISTRITOS_SP`) são **valores literais escritos no código-fonte**, escolhidos para serem
plausíveis em ordem de grandeza. A grade "de satélite" em `demo_netcdf_spatial_clip.py` é um
campo gaussiano gerado com `numpy.random` e semente fixa.

Os números produzidos por este pipeline **não são estimativas epidemiológicas válidas** e não
devem ser citados como tal. O objetivo do repositório é demonstrar o **método** de integração
entre sensoriamento remoto, medição de superfície e desfecho hospitalar, não produzir resultado
científico.

> **Contexto.** Desenvolvido como estudo preparatório para o processo seletivo de estágio do
> Núcleo de Sistemas Eletrônicos Embarcados (NSEE — Instituto Mauá de Tecnologia) em cooperação
> com a Faculdade de Saúde Pública da USP, no âmbito do programa *Early Adopters* da Missão MAIA
> da NASA.

---

## O que este repositório demonstra

| Competência | Onde está | Real ou sintético |
| :--- | :--- | :--- |
| Interpolação espacial IDW implementada do zero | `maia_spatial_engine.py` | **Algoritmo real** |
| Função concentração-resposta e fração atribuível populacional | `maia_spatial_engine.py` | **Formulação real (OMS)** |
| Estruturação de camada vetorial GeoJSON (EPSG:4326) | `pipeline_cetesb_sp.py` | **Formato real** |
| Carregamento automatizado no console Python do QGIS | `qgis_style_loader.py` | **Script funcional** |
| Composição cartográfica em matplotlib, 300 DPI | `maia_spatial_engine.py` | **Real** |
| Concentrações das estações CETESB | literais no código | Sintético |
| Internações SIH/SUS por distrito | literais no código | Sintético |
| Grade de AOD "MAIA" | `numpy.random`, seed 42 | Sintético |
| Fracionamento químico dos aerossóis | percentuais fixos | Sintético |

---

## O que este repositório NÃO é

Explicitado para que ninguém precise descobrir lendo o código:

- **Não lê NetCDF nem HDF5.** Nenhuma dependência de `xarray`, `netCDF4` ou `h5py` é utilizada.
  O recorte espacial opera sobre matriz NumPy gerada em memória.
- **Não faz ingestão automatizada da CETESB.** Não há requisição à API do QUALAR nem raspagem.
- **Não consulta o DATASUS.** As bases de internação não vieram do TabNet nem dos arquivos do SIH.
- **A validação cruzada não valida nada.** O RMSE e o MAE em `demo_netcdf_spatial_clip.py`
  comparam ruído sintético contra valores literais. A métrica é aritmeticamente correta e
  epistemicamente vazia.
- **O fracionamento químico não é especiação.** `calcular_especiacao_maia()` aplica percentuais
  fixos sobre o PM₂.₅. Como as frações nunca variam entre estações, o painel B da figura não
  carrega informação além do próprio PM₂.₅.

---

## Fundamentação do modelo

### 1. Coluna atmosférica e concentração de superfície

Sensores orbitais medem a **Espessura Óptica de Aerossóis (AOD)**, grandeza adimensional que
integra a extinção óptica ao longo da coluna vertical:

$$AOD = \int_0^\infty \sigma_{ext}(z)\, dz$$

A conversão para concentração de superfície depende da altura da Camada Limite Planetária (PBLH)
e do crescimento higroscópico do aerossol:

$$PM_{2.5} \approx \eta \cdot \frac{AOD}{PBLH \cdot f(RH)}, \qquad f(RH) = \left(1 - \frac{RH}{100}\right)^{-\gamma}$$

Esta relação está documentada como fundamentação teórica. **Ela não é aplicada no código**, que
parte diretamente de concentrações de superfície.

### 2. Superfície contínua por Inverso da Distância Ponderada

Implementada em `interpolacao_idw()`, com tratamento do caso degenerate em que o ponto de grade
coincide com uma estação:

$$\hat{Z}(s_0) = \frac{\sum_{i=1}^n w_i Z(s_i)}{\sum_{i=1}^n w_i}, \qquad w_i = \frac{1}{\|s_0 - s_i\|^p}, \quad p = 2$$

### 3. Impacto epidemiológico

Função log-linear da OMS, com limiar de referência $C_0 = 5{,}0\ \mu g/m^3$ e coeficientes
$\beta_{cardio} = 0{,}008$ e $\beta_{resp} = 0{,}011$ por $\mu g/m^3$:

$$RR = \exp\left(\beta \cdot \max(0,\ C - C_0)\right), \qquad PAF = \frac{RR - 1}{RR}, \qquad I_{atrib} = I_{base} \cdot PAF$$

---

## Saída do modelo

![Painel integrado](mapa_analise_integrada_sp.png)

**Figura 1.** **(A)** Superfície contínua de PM₂.₅ interpolada por IDW sobre a grade da RMSP,
com posições de estação e centróides de distrito. **(B)** Fracionamento químico por percentual
fixo. Ambos os painéis operam sobre dados sintéticos.

### Saída numérica sobre dados sintéticos

Os valores abaixo são **produto do modelo alimentado com entradas sintéticas**. Não representam
internações reais e não devem ser interpretados como estimativa de saúde pública.

| Distrito | PM₂.₅ de entrada (µg/m³) | RR cardiovascular | RR respiratório | Saída do modelo (casos/ano) |
| :--- | :---: | :---: | :---: | :---: |
| Itaquera | 17,15 | 1,102 | 1,143 | 1.062 |
| São Mateus | 19,34 | 1,121 | 1,171 | 1.011 |
| Campo Limpo | 18,02 | 1,109 | 1,154 | 795 |
| Santana / Tucuruvi | 17,84 | 1,108 | 1,152 | 674 |
| Mooca | 19,78 | 1,125 | 1,176 | 762 |
| Pinheiros | 18,72 | 1,116 | 1,163 | 563 |
| Sé / República | 20,91 | 1,136 | 1,191 | 484 |

---

## Estrutura

```text
cetesb-air-quality-sp/
├── maia_spatial_engine.py               # IDW, função concentração-resposta, cartografia
├── pipeline_cetesb_sp.py                # Estruturação e exportação GeoJSON / CSV
├── demo_netcdf_spatial_clip.py          # Recorte espacial sobre grade SINTÉTICA
├── qgis_style_loader.py                 # Carregamento no console Python do QGIS
├── cetesb_estacoes_qualidade_ar.geojson # Camada vetorial WGS84 (EPSG:4326)
├── cetesb_estacoes_especiacao_maia.csv  # Fracionamento por percentual fixo
├── exposicao_e_saude_distritos_sp.csv   # Saída do modelo epidemiológico
├── validacao_satelite_cetesb.csv        # Comparação entre duas fontes sintéticas
└── mapa_analise_integrada_sp.png        # Composição cartográfica, 300 DPI
```

---

## Execução

```bash
git clone https://github.com/f1scher01/cetesb-air-quality-sp.git
cd cetesb-air-quality-sp
pip install numpy pandas matplotlib

python maia_spatial_engine.py        # gera CSVs e a composição cartográfica
python demo_netcdf_spatial_clip.py   # recorte espacial sobre grade sintética
```

No QGIS 3.34 LTR, arraste `cetesb_estacoes_qualidade_ar.geojson` para o canvas, ou abra o console
Python com `Ctrl+Alt+P` e execute `qgis_style_loader.py`.

---

## Próximos passos

Na ordem em que agregam valor real ao estudo:

1. **Substituir a grade sintética por NetCDF real.** Baixar um granule de AOD (MODIS MCD19A2 ou
   VIIRS AERDB) no NASA Earthdata, abrir com `xarray`, recortar pelo *bounding box* da RMSP e
   reprojetar. Esta é a lacuna mais relevante do repositório.
2. **Ingerir séries reais da CETESB** pelo sistema QUALAR, substituindo os literais.
3. **Baixar internações reais do SIH/SUS** pelo TabNet, por distrito e por capítulo da CID-10
   (I00–I99 e J00–J99), substituindo as bases inventadas.
4. **Refazer a validação cruzada** com satélite real contra estação real, momento em que o RMSE
   e o MAE passam a significar alguma coisa.
5. **Substituir o fracionamento fixo** por perfis de especiação medidos em campanhas da RMSP.

---

## Autor

**Lucas Fischer Paez**
Graduando em Engenharia Mecânica — Instituto Mauá de Tecnologia (2º ano)
Coeficiente de rendimento 8,23 · Lean Six Sigma Green Belt
Interesses: telemetria, sensoriamento remoto, métodos numéricos e dinâmica de poluentes

[LinkedIn](https://www.linkedin.com/in/lucasfischerpaez) · [GitHub](https://github.com/f1scher01) · fischer.paez@gmail.com
