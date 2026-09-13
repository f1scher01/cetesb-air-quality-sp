"""
Ingestão de AOD real do GOES-19 (ABI L2, NetCDF-4) e recorte para a RMSP.

Fluxo:
    1. lista os arquivos de uma hora no bucket público da NOAA;
    2. baixa o NetCDF (~40 MB, disco completo);
    3. abre as variáveis AOD e DQF pelo driver netCDF do GDAL;
    4. reprojeta da projeção geoestacionária (fixed grid, sweep x) para EPSG:4326;
    5. aplica scale_factor/add_offset e descarta pixels com DQF acima do limite;
    6. grava GeoTIFF float32 com os metadados de origem, pronto para o QGIS.

Roda no Python que acompanha o QGIS (python-qgis-ltr.bat), sem dependências extras.

Uso:
    python goes_aod.py 2026-09-11T19           # primeiro scan da hora, em UTC
    python goes_aod.py caminho/arquivo.nc      # recorta um NetCDF já baixado

Autor: Lucas Fischer Paez
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from osgeo import gdal

import config

gdal.UseExceptions()

VALOR_AUSENTE = -9999.0


def listar_arquivos(momento_utc):
    """Retorna as chaves S3 dos scans de disco completo daquela hora UTC."""
    dia_juliano = momento_utc.timetuple().tm_yday
    prefixo = f"{config.GOES_PRODUTO}/{momento_utc:%Y}/{dia_juliano:03d}/{momento_utc:%H}/"
    resposta = requests.get(config.GOES_BUCKET, params={"list-type": "2", "prefix": prefixo}, timeout=60)
    resposta.raise_for_status()
    return sorted(re.findall(r"<Key>([^<]+\.nc)</Key>", resposta.text))


def baixar(chave, destino=config.DIR_BRUTOS):
    """Baixa um objeto do bucket, pulando se o arquivo já existir localmente."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / Path(chave).name
    if caminho.exists():
        return caminho
    with requests.get(f"{config.GOES_BUCKET}/{chave}", stream=True, timeout=300) as r:
        r.raise_for_status()
        parcial = caminho.with_suffix(".parcial")
        with open(parcial, "wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
        parcial.rename(caminho)
    return caminho


def _reprojetar(nc_path, variavel):
    """Reprojeta uma variável do NetCDF para a grade regular da RMSP (vizinho mais próximo).

    Vizinho mais próximo é deliberado: o DQF é categórico e não pode ser
    interpolado, e o AOD precisa continuar alinhado pixel a pixel com o seu DQF.
    """
    b = config.BBOX_RMSP
    origem = gdal.Open(f'NETCDF:"{nc_path}":{variavel}')
    banda = origem.GetRasterBand(1)
    destino = gdal.Warp(
        "", origem, format="MEM",
        dstSRS="EPSG:4326",
        outputBounds=(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"]),
        xRes=config.RESOLUCAO_GRAUS, yRes=config.RESOLUCAO_GRAUS,
        resampleAlg="near",
        srcNodata=banda.GetNoDataValue(), dstNodata=banda.GetNoDataValue(),
    )
    bruto = destino.GetRasterBand(1).ReadAsArray()
    return bruto, banda.GetScale() or 1.0, banda.GetOffset() or 0.0, banda.GetNoDataValue(), destino


def recortar(nc_path, dqf_maximo=config.DQF_MAXIMO, saida=None):
    """Gera o GeoTIFF de AOD 550 nm sobre a RMSP e devolve um resumo do recorte."""
    nc_path = Path(nc_path)
    info = gdal.Info(str(nc_path), format="json")
    meta = info.get("metadata", {}).get("", {})
    inicio = meta.get("NC_GLOBAL#time_coverage_start", "")

    aod_bruto, escala, offset, nodata, grade = _reprojetar(nc_path, "AOD")
    dqf, *_ = _reprojetar(nc_path, "DQF")

    aod = aod_bruto.astype("float32") * escala + offset
    invalido = (aod_bruto == nodata) | (dqf > dqf_maximo)
    aod[invalido] = VALOR_AUSENTE

    if saida is None:
        rotulo = re.search(r"_s(\d{13})", nc_path.name).group(1)
        saida = config.DIR_PROCESSADOS / f"goes19_aod_rmsp_{rotulo}.tif"
    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    tif = gdal.GetDriverByName("GTiff").Create(
        str(saida), grade.RasterXSize, grade.RasterYSize, 1, gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3"],
    )
    tif.SetGeoTransform(grade.GetGeoTransform())
    tif.SetProjection(grade.GetProjection())
    banda = tif.GetRasterBand(1)
    banda.WriteArray(aod)
    banda.SetNoDataValue(VALOR_AUSENTE)
    banda.SetDescription("AOD 550 nm")
    tif.SetMetadata({
        "fonte": nc_path.name,
        "time_coverage_start": inicio,
        "dqf_maximo": str(dqf_maximo),
        "produto": "NOAA GOES-19 ABI L2+ Aerosol Optical Depth (ABI-L2-AODF)",
    })
    tif.FlushCache()
    tif = None

    validos = aod[~invalido]
    resumo = {
        "arquivo": str(saida),
        "inicio_scan_utc": inicio,
        "pixels_total": int(aod.size),
        "pixels_validos": int(validos.size),
        "cobertura_valida_pct": round(100 * validos.size / aod.size, 1),
        "aod_mediana": round(float(np.median(validos)), 3) if validos.size else None,
        "aod_p90": round(float(np.percentile(validos, 90)), 3) if validos.size else None,
    }
    return resumo


def _momento(texto):
    return datetime.strptime(texto, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    argumento = sys.argv[1]
    if argumento.endswith(".nc"):
        nc = Path(argumento)
    else:
        chaves = listar_arquivos(_momento(argumento))
        if not chaves:
            sys.exit(f"Nenhum arquivo {config.GOES_PRODUTO} para {argumento} UTC.")
        print(f"{len(chaves)} scans na hora; usando {Path(chaves[0]).name}")
        nc = baixar(chaves[0])
    for chave, valor in recortar(nc).items():
        print(f"  {chave:22s} {valor}")
