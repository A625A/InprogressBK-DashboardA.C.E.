import sqlite3
import pandas as pd
import os
import logging
import time
from tqdm import tqdm

# --- Configuración ---
DB_NAME = 'comercio_exterior.db'
CSV_NAME = 'polizas_full.csv'
CHUNK_SIZE = 100000  # Procesar el CSV en trozos para no agotar la memoria
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- 1. Definición del Esquema ---
def create_schema(conn):
    """
    Crea la estructura de la base de datos (tablas e índices)
    según el diagrama ER proporcionado.
    """
    logging.info("Creando esquema de la base de datos...")
    c = conn.cursor()

    # Tablas de dimensiones (Lookup)
    c.execute('''
              CREATE TABLE aduanas
              (
                  id   INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT_NULL UNIQUE
              )
              ''')
    c.execute('''
              CREATE TABLE tipo_regimen
              (
                  id   INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT_NULL UNIQUE
              )
              ''')
    c.execute('''
              CREATE TABLE pais
              (
                  id   INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT_NULL UNIQUE
              )
              ''')
    c.execute('''
              CREATE TABLE sac
              (
                  id          INTEGER PRIMARY KEY AUTOINCREMENT,
                  fraccion    BIGINT NOT_NULL UNIQUE,
                  descripcion TEXT
              )
              ''')
    c.execute('''
              CREATE TABLE tipo_unidad_medida
              (
                  id   INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT_NULL UNIQUE
              )
              ''')

    # Tablas de hechos (Transacciones)
    c.execute('''
              CREATE TABLE polizas
              (
                  id                INTEGER PRIMARY KEY AUTOINCREMENT,
                  correlativo       BIGINT NOT_NULL UNIQUE,
                  fecha_declaracion DATE,
                  tipo_cambio_dolar FLOAT,
                  aduana_id         INTEGER,
                  tipo_regimen_id   INTEGER,
                  FOREIGN KEY (aduana_id) REFERENCES aduanas (id),
                  FOREIGN KEY (tipo_regimen_id) REFERENCES tipo_regimen (id)
              )
              ''')

    c.execute('''
              CREATE TABLE poliza_items
              (
                  id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                  poliza_id                  INTEGER,
                  sac_id                     INTEGER,
                  pais_id                    INTEGER,
                  tipo_unidad_medida_id      INTEGER,
                  cantidad_fraccion          FLOAT,
                  tasa_dai                   FLOAT,
                  valor_dai                  FLOAT,
                  valor_cif_uds              FLOAT,
                  tasa_cif_cantidad_fraccion FLOAT,
                  FOREIGN KEY (poliza_id) REFERENCES polizas (id) ON DELETE CASCADE,
                  FOREIGN KEY (sac_id) REFERENCES sac (id),
                  FOREIGN KEY (pais_id) REFERENCES pais (id),
                  FOREIGN KEY (tipo_unidad_medida_id) REFERENCES tipo_unidad_medida (id)
              )
              ''')

    # Índices para mejorar el rendimiento de los JOINS y búsquedas
    logging.info("Creando índices...")
    c.execute('CREATE INDEX idx_poliza_items_poliza_id ON poliza_items(poliza_id)')
    c.execute('CREATE INDEX idx_poliza_items_sac_id ON poliza_items(sac_id)')
    c.execute('CREATE INDEX idx_poliza_items_pais_id ON poliza_items(pais_id)')

    conn.commit()
    logging.info("Esquema creado exitosamente.")


# --- 2. Proceso ETL ---
def etl_process(conn):
    """
    Ejecuta el proceso ETL:
    1. Lee el CSV en trozos.
    2. Extrae y carga las tablas de dimensión (lookup).
    3. Crea mapas en memoria para los FK.
    4. Carga la tabla de Pólizas (cabeceras).
    5. Carga la tabla de Póliza_Items (detalles).
    """

    # --- Paso 2.1: Extraer y Cargar Dimensiones ---
    logging.info("Iniciando Paso 1: Carga de tablas de dimensión (lookup)...")

    # Usamos sets para guardar solo valores únicos de forma eficiente
    aduanas_set = set()
    tipo_regimen_set = set()
    pais_set = set()
    sac_set = set()
    unidad_medida_set = set()

    logging.info("Leyendo CSV para extraer dimensiones (esto puede tardar)...")
    for chunk in tqdm(pd.read_csv(CSV_NAME, chunksize=CHUNK_SIZE), desc="Extracting Dims"):
        aduanas_set.update(chunk['aduana'].dropna().unique())
        tipo_regimen_set.update(chunk['tipo_regimen'].dropna().unique())
        pais_set.update(chunk['pais'].dropna().unique())
        unidad_medida_set.update(chunk['tipo_unidad_medida'].dropna().unique())

        # Para SAC, guardamos la tupla (fraccion, descripcion)
        sac_chunk = chunk[['sac', 'descripcion']].dropna(subset=['sac'])
        sac_set.update(map(tuple, sac_chunk.values))

    # Cargar dimensiones a la BD
    pd.DataFrame(list(aduanas_set), columns=['name']).to_sql('aduanas', conn, if_exists='append', index=False)
    pd.DataFrame(list(tipo_regimen_set), columns=['name']).to_sql('tipo_regimen', conn, if_exists='append', index=False)
    pd.DataFrame(list(pais_set), columns=['name']).to_sql('pais', conn, if_exists='append', index=False)
    pd.DataFrame(list(unidad_medida_set), columns=['name']).to_sql('tipo_unidad_medida', conn, if_exists='append', index=False)

    # Carga de SAC
    df_sac = pd.DataFrame(list(sac_set), columns=['fraccion', 'descripcion']).drop_duplicates(subset=['fraccion'])
    df_sac.to_sql('sac', conn, if_exists='append', index=False)

    logging.info("Tablas de dimensión cargadas.")

    # --- Paso 2.2: Crear Mapas de FK en Memoria ---
    logging.info("Creando mapas de FK en memoria...")
    aduana_map = pd.read_sql('SELECT id, name FROM aduanas', conn).set_index('name')['id'].to_dict()
    tipo_regimen_map = pd.read_sql('SELECT id, name FROM tipo_regimen', conn).set_index('name')['id'].to_dict()
    pais_map = pd.read_sql('SELECT id, name FROM pais', conn).set_index('name')['id'].to_dict()
    sac_map = pd.read_sql('SELECT id, fraccion FROM sac', conn).set_index('fraccion')['id'].to_dict()
    unidad_medida_map = pd.read_sql('SELECT id, name FROM tipo_unidad_medida', conn).set_index('name')['id'].to_dict()

    # --- Paso 2.3: Cargar Pólizas (Cabeceras) ---
    logging.info("Iniciando Paso 2: Carga de Pólizas (cabeceras)...")

    processed_correlativos = set()

    # Usaremos una lista para inserción en batch
    polizas_batch = []

    for chunk in tqdm(pd.read_csv(CSV_NAME, chunksize=CHUNK_SIZE), desc="Processing Polizas"):
        # Nos quedamos solo con las cabeceras únicas de este chunk
        unique_polizas = chunk.drop_duplicates(subset=['correlativo'])

        for row in unique_polizas.itertuples():
            if row.correlativo not in processed_correlativos:
                polizas_batch.append((
                    row.correlativo,
                    row.fecha_declaracion,
                    row.tipo_cambio_dolar,
                    aduana_map.get(row.aduana),
                    tipo_regimen_map.get(row.tipo_regimen)
                ))
                processed_correlativos.add(row.correlativo)

    # Insertar el batch en la BD
    conn.executemany(
        'INSERT INTO polizas (correlativo, fecha_declaracion, tipo_cambio_dolar, aduana_id, tipo_regimen_id) VALUES (?, ?, ?, ?, ?)',
        polizas_batch
    )
    conn.commit()
    logging.info(f"Cargadas {len(processed_correlativos)} pólizas únicas.")

    # --- Paso 2.4: Crear Mapa de Pólizas y Cargar Items ---
    logging.info("Creando mapa de Poliza ID...")
    poliza_id_map = pd.read_sql('SELECT id, correlativo FROM polizas', conn).set_index('correlativo')['id'].to_dict()

    logging.info("Iniciando Paso 3: Carga de Póliza Items (detalles)...")

    for chunk in tqdm(pd.read_csv(CSV_NAME, chunksize=CHUNK_SIZE), desc="Processing Items"):
        # Mapear todos los FKs
        chunk['poliza_id'] = chunk['correlativo'].map(poliza_id_map)
        chunk['sac_id'] = chunk['sac'].map(sac_map)
        chunk['pais_id'] = chunk['pais'].map(pais_map)
        chunk['tipo_unidad_medida_id'] = chunk['tipo_unidad_medida'].map(unidad_medida_map)

        # Seleccionar columnas finales
        items_df = chunk[[
            'poliza_id', 'sac_id', 'pais_id', 'tipo_unidad_medida_id',
            'cantidad_fraccion', 'tasa_dai', 'valor_dai', 'valor_cif_uds',
            'tasa_cif_cantidad_fraccion'
        ]]

        # Cargar a la BD
        items_df.to_sql('poliza_items', conn, if_exists='append', index=False)

    logging.info("Carga de Póliza Items completada.")


# --- 3. Ejecución Principal ---
def main():
    start_time = time.time()

    # Eliminar BD antigua si existe
    if os.path.exists(DB_NAME):
        logging.info(f"Eliminando base de datos antigua '{DB_NAME}'...")
        os.remove(DB_NAME)

    # Validar que el CSV existe
    if not os.path.exists(CSV_NAME):
        logging.error(f"Error: No se encontró el archivo '{CSV_NAME}'.")
        logging.error("Por favor, asegúrate de que el archivo CSV esté en la misma carpeta que este script.")
        return

    conn = None
    try:
        # Crear conexión y esquema
        conn = sqlite3.connect(DB_NAME)
        create_schema(conn)

        # Ejecutar ETL
        etl_process(conn)

    except Exception as e:
        logging.error(f"Ocurrió un error durante el proceso: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    end_time = time.time()
    logging.info(f"Proceso completado en {end_time - start_time:.2f} segundos.")
    logging.info(f"Base de datos '{DB_NAME}' creada y poblada exitosamente.")


if __name__ == '__main__':
    main()
