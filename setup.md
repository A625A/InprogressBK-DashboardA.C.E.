# Prueba Técnica Backend - Setup Inicial

Bienvenido a la prueba técnica. Este directorio contiene el script (setup.py) necesario para generar la base de datos que utilizarás durante el desafío.

El objetivo es crear un archivo `comercio_exterior.db` (SQLite) a partir de un archivo CSV de gran tamaño.

> ⚠️ Importante: Archivo de Datos
> 
> Debido al gran tamaño del archivo de datos (1.7M+ de filas), se encuentra comprimido.

> Archivo: polizas_full.csv.zip

**Acción Requerida**: Antes de continuar, debes descomprimir este archivo. El script espera encontrar polizas_full.csv en la misma carpeta.

## Instrucciones de Setup

Este proyecto utiliza uv para la gestión del entorno virtual y las dependencias. El pyproject.toml adjunto define todo lo necesario.

### Instalar uv (si no lo tienes):

```Bash
pip install uv
```

> Para más información sobre uv, puedes consultar la documentación oficial de uv.

### Crear Entorno e Instalar Dependencias: 

UV puede crear el entorno e instalar las dependencias (pandas, tqdm, etc.) en un solo paso usando el pyproject.toml.

```Bash

# 1. Crea el entorno virtual (usualmente en .venv)
uv venv

# 2. Instala las dependencias definidas en pyproject.toml
uv pip sync
```

### Activar el Entorno Virtual:

Windows (PowerShell): `.venv\Scripts\Activate.ps1`

Windows (CMD): `.venv\Scripts\activate.bat`

macOS/Linux: source `.venv/bin/activate`

### Ejecutar el Script de Carga: 

Una vez activado el entorno y con el .csv descomprimido, ejecuta el script:

```Bash
python setup.py
```

Este script leerá polizas_full.csv, procesará los 1.7 millones de filas, normalizará los datos y creará la base de datos comercio_exterior.db.

> Nota: El script mostrará una barra de progreso. Ten paciencia, el proceso completo puede tardar varios minutos dependiendo de tu máquina.

¡Una vez que tengas el archivo comercio_exterior.db, estarás listo para comenzar con la prueba principal!