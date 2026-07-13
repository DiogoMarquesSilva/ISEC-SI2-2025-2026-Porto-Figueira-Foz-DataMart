#!/usr/bin/env python3
# codificação: utf-8

import os
import sys
import mysql.connector as mysql
import pyodbc
import csv
from datetime import datetime

# Variaveis de ligação aos SGBD
# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1") 
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306")) 
MYSQL_USER = os.getenv("MYSQL_USER", "root") 
MYSQL_PWD  = os.getenv("MYSQL_PWD",  "1234") 
MYSQL_DB   = os.getenv("MYSQL_DB",   "TP_G2") 

# SQL Server
MSSQL_HOST   = os.getenv("MSSQL_HOST", "127.0.0.1") 
MSSQL_PORT   = int(os.getenv("MSSQL_PORT", "1433")) 
MSSQL_USER   = os.getenv("MSSQL_USER", "sa") 
MSSQL_PWD    = os.getenv("MSSQL_PWD",  "1234") 
MSSQL_DB     = os.getenv("MSSQL_DB",   "TP_G2") 
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server") 

def get_mysql_conn():
    print("A ligar ao MySQL...")
    return mysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PWD, database=MYSQL_DB, autocommit=True, charset="utf8mb4")

def get_mssql_conn():
    print("A ligar ao SQL Server...")
    conn_str = f"DRIVER={{{MSSQL_DRIVER}}};SERVER={MSSQL_HOST},{MSSQL_PORT};DATABASE={MSSQL_DB};UID={MSSQL_USER};PWD={MSSQL_PWD};TrustServerCertificate=Yes;"
    return pyodbc.connect(conn_str)

# 1 - Retirar os dados da base de dados operacional mysql
def fetch_from_mysql(conn):
    print("A extrair dados do MySQL...")
    
    mapa_tipo_viagem = {}
    mapa_tempo = {}

    try: 
        cur = conn.cursor(dictionary=True) 

        # 1. DIM BARCO
        cur.execute("SELECT idbarco, nomebarco, tamanhobarco, paisbarco, tipobarco, capacidadeteu FROM barco")
        barco = [(
            r["idbarco"], 
            r["nomebarco"], 
            round(float(r["tamanhobarco"]), 2) if r["tamanhobarco"] else 0.0, 
            r["paisbarco"], 
            r["tipobarco"], 
            r["capacidadeteu"]
        ) for r in cur.fetchall()] 

        # 2. DIM LOCALIZAÇÃO
        cur.execute("""SELECT DISTINCT 
                l_origem.idlocalizacao as idorigem, 
                CONCAT('Porto - ', l_origem.cidade, ' - ', l_origem.pais) as nomeporto,
                l_origem.pais as pais
            FROM localizacao l_origem
            JOIN viagem v ON v.localizacao_idlocalizacao = l_origem.idlocalizacao
            JOIN localizacao l_destino ON v.localizacao_idlocalizacao1 = l_destino.idlocalizacao
            WHERE 
                l_destino.cidade LIKE '%figfoz%' AND l_destino.pais = 'Portugal'
            """)
        localizacao = [(r["idorigem"], r["nomeporto"], r["pais"]) for r in cur.fetchall()]

        # 3. DIM EMPRESAS
        cur.execute("SELECT idempresabarco, nomeempresabarco, paisempresabarco, emailempresabarco FROM empresabarco")
        empresas = [(r["idempresabarco"], r["nomeempresabarco"], r["paisempresabarco"], r["emailempresabarco"]) for r in cur.fetchall()] 

        # 4. DIM CONDUTOR
        cur.execute("SELECT idcondutor, nomecondutor, idadecondutor, certificacao FROM condutor")
        condutores = [(r["idcondutor"], r["nomecondutor"], r["idadecondutor"], r["certificacao"]) for r in cur.fetchall()] 

        # 5. DIM TIPO VIAGEM
        cur.execute("SELECT DISTINCT tipoviagem FROM viagem")
        tipos = cur.fetchall()
        tipos_viagem = []
        for idx, row in enumerate(tipos, start=1):
            descricao = row["tipoviagem"]
            tipos_viagem.append((idx, descricao))
            mapa_tipo_viagem[descricao] = idx
            
        # 6. DIM TEMPO
        cur.execute("""
            SELECT DISTINCT v.datachegada
            FROM viagem v
            JOIN localizacao l_dest ON v.localizacao_idlocalizacao1 = l_dest.idlocalizacao
            WHERE v.status = 'concluida'
              AND l_dest.cidade LIKE '%figfoz%'
              AND l_dest.pais = 'Portugal' 
              AND v.datachegada IS NOT NULL
            ORDER BY v.datachegada ASC""")
        tempo = cur.fetchall()
        lista_tempo = []
        for id_seq, row in enumerate(tempo, start=1):
            data_obj = row['datachegada']
            registo = (id_seq, data_obj, data_obj.day, data_obj.month, data_obj.year, 1 if data_obj.month <= 6 else 2)
            lista_tempo.append(registo)
            mapa_tempo[data_obj] = id_seq
            
        # 7. FACT VIAGENS
        cur.execute("""
            SELECT 
                v.idviagem,
                v.datachegada,
                v.tipoviagem,
                v.barco_idbarco,
                v.condutor_idcondutor,
                v.localizacao_idlocalizacao,
                b.empresabarco_idempresabarco,
                DATEDIFF(v.datachegada, v.datapartida) as dias_viagem,
                COALESCE(SUM(t.valor), 0) as receita_total,
                COUNT(DISTINCT c.idcontentor) as num_contentores,
                COALESCE(SUM(c.pesocontentor), 0) as peso_total
            FROM viagem v
            JOIN barco b ON v.barco_idbarco = b.idbarco 
            JOIN localizacao l_dest ON v.localizacao_idlocalizacao1 = l_dest.idlocalizacao
            LEFT JOIN taxas t ON t.viagem_idviagem = v.idviagem
            LEFT JOIN contentores c ON c.viagem_idviagem = v.idviagem
            WHERE 
                v.status = 'concluida'
                AND l_dest.cidade LIKE '%figfoz%' 
                AND l_dest.pais = 'Portugal'
            GROUP BY 
                v.idviagem, v.datachegada, v.datapartida, v.tipoviagem, 
                v.barco_idbarco, v.condutor_idcondutor, v.localizacao_idlocalizacao,
                b.empresabarco_idempresabarco""")
            
        viagens_raw = cur.fetchall()
        viagens_facto = []
        
        for row in viagens_raw:
            id_tempo = mapa_tempo.get(row['datachegada'], -1)
            id_tipo = mapa_tipo_viagem.get(row['tipoviagem'], -1)
            
            receita_eur = round(float(row['receita_total']) * 0.86, 2)
            peso_total  = round(float(row['peso_total']), 2) 
            
            registo_facto = (
                row['barco_idbarco'],
                row['localizacao_idlocalizacao'],
                row['condutor_idcondutor'],
                row['empresabarco_idempresabarco'], 
                id_tempo,
                id_tipo,
                row['idviagem'],
                receita_eur,
                int(row['num_contentores']),
                peso_total,
                int(row['dias_viagem']),
                1
            )
            viagens_facto.append(registo_facto)
        
        return barco, localizacao, empresas, condutores, tipos_viagem, lista_tempo, viagens_facto

    finally:
        pass

# 2 CRIAÇÃO DAS TABELAS DE STAGING 
def ensure_staging(conn):
    print("A criar/limpar as tabelas de Staging...")
    cur = conn.cursor() 

    cur.execute("""
        IF OBJECT_ID('stg_barco','U') IS NULL
        CREATE TABLE stg_barco (
            id_barco_bk    INT, 
            nome_barco     NVARCHAR(100),
            tamanho        DECIMAL(10,2),
            pais           NVARCHAR(50),
            tipo_barco     NVARCHAR(50),
            capacidade_teu INT
        );
        TRUNCATE TABLE stg_barco;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_localizacao','U') IS NULL
        CREATE TABLE stg_localizacao (
            id_localizacao_bk INT,
            nome_porto        NVARCHAR(150),
            pais              NVARCHAR(50)
        );
        TRUNCATE TABLE stg_localizacao;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_empresa','U') IS NULL
        CREATE TABLE stg_empresa (
            id_empresa_bk  INT,
            nome_empresa   NVARCHAR(100),
            pais_empresa   NVARCHAR(100),
            email_empresa  NVARCHAR(100)
        );
        TRUNCATE TABLE stg_empresa;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_condutor','U') IS NULL
        CREATE TABLE stg_condutor (
            id_condutor_bk   INT,
            nome_condutor    NVARCHAR(100),
            idade            INT,
            certificacao     NVARCHAR(100)
        );
        TRUNCATE TABLE stg_condutor;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_tipo_viagem','U') IS NULL
        CREATE TABLE stg_tipo_viagem (
            id_tipo_seq INT,
            descricao   NVARCHAR(50)
        );
        TRUNCATE TABLE stg_tipo_viagem;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_tempo','U') IS NULL
        CREATE TABLE stg_tempo (
            id_tempo_seq  INT,
            data_completa DATE,
            dia           INT,
            mes           INT,
            ano           INT,
            semestre      INT
        );
        TRUNCATE TABLE stg_tempo;
    """)
    cur.execute("""
        IF OBJECT_ID('stg_fact_viagens','U') IS NULL
        CREATE TABLE stg_fact_viagens (
            fk_barco      INT,
            fk_origem     INT,
            fk_condutor   INT,
            fk_empresa    INT,
            fk_tempo      INT,
            fk_tipo       INT,
            dd_id_viagem  INT,
            receita_eur   DECIMAL(12,2),
            num_cont      INT,
            peso_total    DECIMAL(12,2),
            dias_viagem   INT,
            contagem      INT
        );
        TRUNCATE TABLE stg_fact_viagens;
    """)
    conn.commit()
    print("Tabelas de Staging recriadas com sucesso.")

# Função para preencher as tabelas de staging 
def bulk_load_staging(conn, barco, localizacao, empresas, condutores, tipos_viagem, lista_tempo, viagens_facto):
    print(" A carregar dados para as tabelas de Staging")
    cur = conn.cursor() 
    cur.fast_executemany = True 
    if barco: cur.executemany("INSERT INTO stg_barco VALUES (?, ?, ?, ?, ?, ?)", barco)
    if localizacao: cur.executemany("INSERT INTO stg_localizacao VALUES (?, ?, ?)", localizacao)
    if empresas: cur.executemany("INSERT INTO stg_empresa VALUES (?, ?, ?, ?)", empresas)
    if condutores: cur.executemany("INSERT INTO stg_condutor VALUES (?, ?, ?, ?)", condutores)
    if tipos_viagem: cur.executemany("INSERT INTO stg_tipo_viagem VALUES (?, ?)", tipos_viagem)
    if lista_tempo: cur.executemany("INSERT INTO stg_tempo VALUES (?, ?, ?, ?, ?, ?)", lista_tempo)
    else: print("AVISO: Lista de Tempo vazia.")
    if viagens_facto: cur.executemany("INSERT INTO stg_fact_viagens VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", viagens_facto)
    else: print("AVISO: Lista de Factos vazia.")
    conn.commit()
    print(f"Carga Staging: {len(viagens_facto)} factos carregados.")

# Insere ou atualiza as dimensões na Dw do SQLServer
def insert_dimensions(conn):
    print("A processar Dimensões (Upsert)")
    cur = conn.cursor()
    try:
        cur.execute("SET XACT_ABORT ON;")  # Garantir o rollback automático se algo falhar

        # 1. DIM BARCO
        cur.execute("""
            UPDATE target
            SET NomeBarco     = src.nome_barco,
                TamanhoBarco  = src.tamanho,
                PaisBarco     = src.pais,
                TipoBarco     = src.tipo_barco,
                CapacidadeTEU = src.capacidade_teu
            FROM barco AS target
            INNER JOIN stg_barco AS src ON target.idbarco = src.id_barco_bk;
        """)
        cur.execute("""
            INSERT INTO barco (idbarco, nomebarco, tamanhobarco, paisbarco, tipobarco, capacidadeteu)
            SELECT src.id_barco_bk, src.nome_barco, src.tamanho, src.pais, src.tipo_barco, src.capacidade_teu
            FROM stg_barco AS src
            WHERE NOT EXISTS (SELECT 1 FROM barco t WHERE t.idbarco = src.id_barco_bk);
        """)

        # 2. DIM LOCALIZACAO
        cur.execute("""
            UPDATE target
            SET NomePorto = src.nome_porto,
                Pais      = src.pais
            FROM localizacaoorigem AS target
            INNER JOIN stg_localizacao AS src ON target.idorigem = src.id_localizacao_bk;
        """)
        cur.execute("""
            INSERT INTO localizacaoorigem (idorigem, nomeporto, pais)
            SELECT src.id_localizacao_bk, src.nome_porto, src.pais
            FROM stg_localizacao AS src
            WHERE NOT EXISTS (SELECT 1 FROM localizacaoorigem t WHERE t.idorigem = src.id_localizacao_bk);
        """)

        # 3. DIM EMPRESA
        cur.execute("""
            UPDATE target
            SET NomeEmpresaBarco = src.nome_empresa,
                PaisEmpresa      = src.pais_empresa,
                EmailEmpresa     = src.email_empresa
            FROM empresabarco AS target
            INNER JOIN stg_empresa AS src ON target.idempresabarco = src.id_empresa_bk;
        """)
        cur.execute("""
            INSERT INTO empresabarco (idempresabarco, nomeempresabarco, paisempresa, emailempresa)
            SELECT src.id_empresa_bk, src.nome_empresa, src.pais_empresa, src.email_empresa
            FROM stg_empresa AS src
            WHERE NOT EXISTS (SELECT 1 FROM empresabarco t WHERE t.idempresabarco = src.id_empresa_bk);
        """)

        # 4. DIM CONDUTOR
        cur.execute("""
            UPDATE target
            SET NomeCondutor    = src.nome_condutor,
                IdadeCondutor   = src.idade,
                TipoCertificado = src.certificacao
            FROM condutor AS target
            INNER JOIN stg_condutor AS src ON target.idcondutor = src.id_condutor_bk;
        """)
        cur.execute("""
            INSERT INTO condutor (idcondutor, nomecondutor, idadecondutor, sexo, tipocertificado)
            SELECT src.id_condutor_bk, src.nome_condutor, src.idade, 'U', src.certificacao
            FROM stg_condutor AS src
            WHERE NOT EXISTS (SELECT 1 FROM condutor t WHERE t.idcondutor = src.id_condutor_bk);
        """)

        # 5. DIM TIPO VIAGEM
        cur.execute("""
            UPDATE target
            SET DescricaoTipoViagem = src.descricao
            FROM tipoviagem AS target
            INNER JOIN stg_tipo_viagem AS src ON target.idtipoviagem = src.id_tipo_seq;
        """)
        cur.execute("""
            INSERT INTO tipoviagem (idtipoviagem, descricaotipoviagem)
            SELECT src.id_tipo_seq, src.descricao
            FROM stg_tipo_viagem AS src
            WHERE NOT EXISTS (SELECT 1 FROM tipoviagem t WHERE t.idtipoviagem = src.id_tipo_seq);
        """)

        # 6. DIM TEMPO
        cur.execute("""
            UPDATE target
            SET DataCompleta = src.data_completa,
                Ano          = src.ano,
                Semestre     = src.semestre,
                Mes          = src.mes,
                Dia          = src.dia
            FROM tempo AS target
            INNER JOIN stg_tempo AS src ON target.idtempo = src.id_tempo_seq;
        """)
        cur.execute("""
            INSERT INTO tempo (idtempo, DataCompleta, Ano, Semestre, Mes, Dia)
            SELECT src.id_tempo_seq, src.data_completa, src.ano, src.semestre, src.mes, src.dia
            FROM stg_tempo AS src
            WHERE NOT EXISTS (SELECT 1 FROM tempo t WHERE t.idtempo = src.id_tempo_seq);
        """)

        conn.commit()
        print("Dimensões atualizadas com sucesso.")
    except Exception as e:
        print(f"Erro ao inserir dimensões: {e}")
        conn.rollback()
        raise

# atualiza a tabela de factos a partir da tabela de staging
def load_fact(conn, full_reload=True):
    print("A carregar Tabela de Factos (viagens)")
    cur = conn.cursor() 
    if full_reload: cur.execute("TRUNCATE TABLE viagens;")# Evita duplicação (carga full)
    
    cur.execute("""
        INSERT INTO viagens (
            receitataxas, numcontentores, teutotal, contagemviagens, numdias,
            tempo_idtempo, localizacaoorigem_idorigem, tipoviagem_idtipoviagem,
            empresabarco_idempresabarco, condutor_idcondutor, barco_idbarco
        )
        SELECT
            s.receita_eur, s.num_cont, s.peso_total, s.contagem, s.dias_viagem,
            s.fk_tempo, s.fk_origem, s.fk_tipo, s.fk_empresa, s.fk_condutor, s.fk_barco
        FROM stg_fact_viagens s;
    """)
    conn.commit()
    print("Tabela de Factos carregada com sucesso.")
    
    
# Função auxiliar para apagar as tabelas de staging
def erase_stg(conn):
    print("A eliminar tabelas de Staging...")
    sql = r"""
        IF OBJECT_ID('dbo.stg_fact_viagens', 'U') IS NOT NULL DROP TABLE dbo.stg_fact_viagens;
        IF OBJECT_ID('dbo.stg_tempo', 'U') IS NOT NULL DROP TABLE dbo.stg_tempo;
        IF OBJECT_ID('dbo.stg_tipo_viagem', 'U') IS NOT NULL DROP TABLE dbo.stg_tipo_viagem;
        IF OBJECT_ID('dbo.stg_condutor', 'U') IS NOT NULL DROP TABLE dbo.stg_condutor;
        IF OBJECT_ID('dbo.stg_empresa', 'U') IS NOT NULL DROP TABLE dbo.stg_empresa;
        IF OBJECT_ID('dbo.stg_localizacao', 'U') IS NOT NULL DROP TABLE dbo.stg_localizacao;
        IF OBJECT_ID('dbo.stg_barco', 'U') IS NOT NULL DROP TABLE dbo.stg_barco;
    """
    try:
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        print("Tabelas de Staging eliminadas com sucesso.")
    except Exception as e:
        print(f"Erro ao eliminar tabelas de staging: {e}")
        conn.rollback()

# Função auxiliar para apagar e recriar as tabelas da DW (Data Mart)
def erase_dw(conn):
    print("A recriar tabelas do Data Mart (DW) com tamanhos corrigidos...")
    sql = r"""
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;
        IF OBJECT_ID(N'dbo.viagens', N'U') IS NOT NULL DROP TABLE dbo.viagens;
        IF OBJECT_ID(N'dbo.tempo', N'U') IS NOT NULL DROP TABLE dbo.tempo;
        IF OBJECT_ID(N'dbo.localizacaoorigem', N'U') IS NOT NULL DROP TABLE dbo.localizacaoorigem;
        IF OBJECT_ID(N'dbo.barco', N'U') IS NOT NULL DROP TABLE dbo.barco;
        IF OBJECT_ID(N'dbo.condutor', N'U') IS NOT NULL DROP TABLE dbo.condutor;
        IF OBJECT_ID(N'dbo.empresabarco', N'U') IS NOT NULL DROP TABLE dbo.empresabarco;
        IF OBJECT_ID(N'dbo.tipoviagem', N'U') IS NOT NULL DROP TABLE dbo.tipoviagem;
        
        CREATE TABLE dbo.tempo (idtempo INTEGER PRIMARY KEY, datacompleta DATE, semestre INTEGER, 
                                ano INTEGER, mes INTEGER, dia INTEGER);
        CREATE TABLE dbo.localizacaoorigem (idorigem INTEGER PRIMARY KEY, nomeporto NVARCHAR(60), 
                                            pais NVARCHAR(16));
        CREATE TABLE dbo.barco (idbarco INTEGER PRIMARY KEY, nomebarco NVARCHAR(20), 
                                tamanhobarco DECIMAL(10,2), paisbarco NVARCHAR(16), tipobarco NVARCHAR(19),
                                capacidadeteu INTEGER);
        CREATE TABLE dbo.condutor (idcondutor INTEGER PRIMARY KEY, nomecondutor NVARCHAR(27), 
                                   idadecondutor INTEGER, sexo VARCHAR(3), tipocertificado NVARCHAR(18));
        CREATE TABLE dbo.empresabarco (idempresabarco INTEGER PRIMARY KEY, nomeempresabarco NVARCHAR(20),
                                       paisempresa NVARCHAR(18), emailempresa NVARCHAR(33));
        CREATE TABLE dbo.tipoviagem (idtipoviagem INTEGER PRIMARY KEY, descricaotipoviagem NVARCHAR(13));

        CREATE TABLE dbo.viagens (
            idviagens                   INTEGER IDENTITY(1,1) PRIMARY KEY,
            receitataxas                DECIMAL(10,2),
            numcontentores              INTEGER,
            teutotal                    DECIMAL(10,2), 
            contagemviagens             INTEGER,
            numdias                     INTEGER,
            tempo_idtempo               INTEGER NOT NULL,
            localizacaoorigem_idorigem  INTEGER NOT NULL,
            tipoviagem_idtipoviagem     INTEGER NOT NULL,
            empresabarco_idempresabarco INTEGER NOT NULL,
            condutor_idcondutor         INTEGER NOT NULL,
            barco_idbarco               INTEGER NOT NULL,
            CONSTRAINT FK_Viagens_Tempo FOREIGN KEY (tempo_idtempo) REFERENCES dbo.tempo(idtempo),
            CONSTRAINT FK_Viagens_Origem FOREIGN KEY (localizacaoorigem_idorigem) REFERENCES dbo.localizacaoorigem(idorigem),
            CONSTRAINT FK_Viagens_Tipo FOREIGN KEY (tipoviagem_idtipoviagem) REFERENCES dbo.tipoviagem(idtipoviagem),
            CONSTRAINT FK_Viagens_Empresa FOREIGN KEY (empresabarco_idempresabarco) REFERENCES dbo.empresabarco(idempresabarco),
            CONSTRAINT FK_Viagens_Cond FOREIGN KEY (condutor_idcondutor) REFERENCES dbo.condutor(idcondutor),
            CONSTRAINT FK_Viagens_Barco FOREIGN KEY (barco_idbarco) REFERENCES dbo.barco(idbarco)
        );
        CREATE INDEX IX_Viagens_Tempo ON dbo.viagens(tempo_idtempo);
        CREATE INDEX IX_Viagens_Barco ON dbo.viagens(barco_idbarco);
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        THROW;
    END CATCH;
    """
    cur = conn.cursor()
    cur.execute(sql)
    print("Tabelas do DW recriadas com sucesso.")
    conn.commit()

# Função para carregar o "estado atual" do Data Mart
# Cria dicionários com TODOS os atributos para garantir unicidade absoluta
def get_sql_lookups(conn):
    print("A carregar contexto atual do SQL Server...")
    cur = conn.cursor()
    
    lookups = {
        'barco': {},      'max_barco': 0,
        'condutor': {},   'max_condutor': 0,
        'localizacao': {},'max_localizacao': 0,
        'tempo': {},      'max_tempo': 0,
        'tipo': {},       'max_tipo': 0,
        'empresa': {}, 'max_empresa': 0
    }

    # BARCO: Chave = (nome, tipo, capacidade)
    try:
        cur.execute("SELECT idbarco, nomebarco, tipobarco, capacidadeteu FROM barco")
        for r in cur.fetchall():
            key = (r[1], r[2], r[3]) # Tuplo para comparação exata
            lookups['barco'][key] = r[0]
            if r[0] > lookups['max_barco']: lookups['max_barco'] = r[0]
    except: pass

    # CONDUTOR: Chave = (nome, idade, sexo, certificado)
    try:
        cur.execute("SELECT idcondutor, nomecondutor, idadecondutor, sexo, tipocertificado FROM condutor")
        for r in cur.fetchall():
            key = (r[1], r[2], r[3], r[4]) # COMPARA TUDO
            lookups['condutor'][key] = r[0]
            if r[0] > lookups['max_condutor']: lookups['max_condutor'] = r[0]
    except: pass

    # LOCALIZACAO: Chave = (porto, pais)
    try:
        cur.execute("SELECT idorigem, nomeporto, pais FROM localizacaoorigem")
        for r in cur.fetchall():
            key = (r[1], r[2])
            lookups['localizacao'][key] = r[0]
            if r[0] > lookups['max_localizacao']: lookups['max_localizacao'] = r[0]
    except: pass

    # TEMPO: Chave = 'YYYY-MM-DD'
    try:
        cur.execute("SELECT idtempo, datacompleta FROM tempo")
        for r in cur.fetchall():
            d_str = r[1].strftime('%Y-%m-%d')
            lookups['tempo'][d_str] = r[0]
            if r[0] > lookups['max_tempo']: lookups['max_tempo'] = r[0]
    except: pass
    
    # TIPO VIAGEM
    try:
        cur.execute("SELECT idtipoviagem, descricaotipoviagem FROM tipoviagem")
        for r in cur.fetchall():
            lookups['tipo'][r[1]] = r[0]
            if r[0] > lookups['max_tipo']: lookups['max_tipo'] = r[0]
    except: pass

    try:
        cur.execute("SELECT idempresabarco, nomeempresabarco, paisempresa, emailempresa FROM empresabarco")
        for r in cur.fetchall():
            key = (r[1], r[2], r[3]); lookups['empresa'][key] = r[0]
            if r[0] > lookups['max_empresa']: lookups['max_empresa'] = r[0]
    except: pass

    return lookups

# Função Principal de processamento do CSV
def process_csv_incremental(file_path, lookups):
    print(f"A processar CSV '{file_path}'...")
    
    # Listas para INSERIR NOVO (Dimensões)
    new_barcos = []
    new_conds = []
    new_locs = []
    new_tempos = []
    new_tipos = []
    new_empresas = []
    
    # Lista para INSERIR FACTOS
    new_factos = []

    # Contadores locais
    cid_barco = lookups['max_barco']
    cid_cond = lookups['max_condutor']
    cid_loc = lookups['max_localizacao']
    cid_tempo = lookups['max_tempo']
    cid_tipo = lookups['max_tipo']
    cid_emp = lookups['max_empresa']

    # 1. Garantir que existe "Empresa Padrão" para o CSV
    emp_std_key = ("Empresa Desconhecida", "N/A", "N/A")
    if emp_std_key in lookups['empresa']:
        id_empresa_std = lookups['empresa'][emp_std_key]
    else:
        cid_emp += 1; id_empresa_std = cid_emp
        lookups['empresa'][emp_std_key] = id_empresa_std
        new_empresas.append((id_empresa_std, "Empresa Desconhecida", "N/A", "N/A"))

    # 2. Garantir que existe "Tipo Viagem Padrão" para o CSV
    tipo_std_key = "Viagem CSV"
    if tipo_std_key in lookups['tipo']:
        id_tipo_std = lookups['tipo'][tipo_std_key]
    else:
        cid_tipo += 1; id_tipo_std = cid_tipo
        lookups['tipo'][tipo_std_key] = id_tipo_std
        new_tipos.append((id_tipo_std, tipo_std_key))
        
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                # 1. FILTRO: Destino tem de ser Figueira / Portugal
                # O CSV usa 'FigueiraDaFoz' 
                if 'Figueira' not in row['cidade_destino'] or row['pais_destino'] != 'Portugal':
                    continue

                # 2. TRATAMENTO DE DIMENSÕES (Verificar se EXISTE EXATAMENTE IGUAL)

                # CONDUTOR (Nome + Idade + Sexo + Certificado)
                c_key = (row['nomecondutor'], int(row['idadecondutor']), row['sexo'], row['certificacao'])
                if c_key in lookups['condutor']:
                    id_cond = lookups['condutor'][c_key]
                else:
                    cid_cond += 1
                    id_cond = cid_cond
                    lookups['condutor'][c_key] = id_cond
                    # Adicionar à lista para INSERT SQL
                    new_conds.append((id_cond, row['nomecondutor'], int(row['idadecondutor']), row['sexo'], row['certificacao']))

                # BARCO (Nome + Tipo + Capacidade)
                b_cap = int(row['capacidadeteu']) if row['capacidadeteu'] else 0
                b_key = (row['nomebarco'], row['tipobarco'], b_cap)
                
                if b_key in lookups['barco']:
                    id_barco = lookups['barco'][b_key]
                else:
                    cid_barco += 1
                    id_barco = cid_barco
                    lookups['barco'][b_key] = id_barco
                    # id, nome, tamanho, pais, tipo, capacidade
                    new_barcos.append((id_barco, row['nomebarco'], 0.0, 'Desconhecido', row['tipobarco'], b_cap))

                # LOCALIZAÇÃO ORIGEM (Cidade + Pais)
                l_key = (row['cidade_origem'], row['pais_origem'])
                if l_key in lookups['localizacao']:
                    id_loc = lookups['localizacao'][l_key]
                else:
                    cid_loc += 1
                    id_loc = cid_loc
                    lookups['localizacao'][l_key] = id_loc
                    nome_porto_formatado = f"Porto - {row['cidade_origem']} - {row['pais_origem']}"                    
                    new_locs.append((id_loc, nome_porto_formatado, row['pais_origem']))

                # TEMPO (Data Chegada)
                try:
                    dt = datetime.strptime(row['datachegada'], '%d/%m/%Y').date()
                    t_key = dt.strftime('%Y-%m-%d')
                except: continue # Data inválida, salta linha

                if t_key in lookups['tempo']:
                    id_tempo = lookups['tempo'][t_key]
                else:
                    cid_tempo += 1
                    id_tempo = cid_tempo
                    lookups['tempo'][t_key] = id_tempo
                    sem = 1 if dt.month <= 6 else 2
                    new_tempos.append((id_tempo, dt, dt.year, sem, dt.month, dt.day))

                # 3. PREPARAR FACTO (Métricas)
                
                # Moeda: Converter USD -> EUR
                try:
                    val_str = row['taxa'].replace('.', '').replace(',', '.') # remove milhar, troca virgula
                    receita = round(float(val_str) * 0.86, 2)
                except: receita = 0.0

                # Dias: Chegada - Partida
                try:
                    d_part = datetime.strptime(row['datapartida'], '%d/%m/%Y').date()
                    dias = (dt - d_part).days
                except: dias = 0
                
                #Contentores
                try: num_cont = int(row.get('numerocontentares', 0)) # default 0
                except: num_cont = 0
                
                #Peso
                try: peso = float(row.get('peso', '0').replace(',', '.')) # default 0.0
                except: peso = 0.0

                facto = (
                    receita, # receitataxas
                    num_cont,       # numcontentores 
                    peso,     # teutotal
                    1,       # contagem
                    dias,    # numdias
                    id_tempo, id_loc, id_tipo_std, id_empresa_std, id_cond, id_barco
                )
                new_factos.append(facto)
                
        return new_barcos, new_conds, new_locs, new_tempos, new_tipos, new_empresas, new_factos

    except Exception as e:
        print(f"Erro CSV: {e}")
        return [], [], [], [], [], [], []

# Função para Inserir os Novos Dados no SQL Server
def load_csv_to_sql(conn, n_barcos, n_conds, n_locs, n_tempos, n_tipos,n_empresas, n_factos):
    print("A inserir dados do CSV no SQL Server...")
    cur = conn.cursor()
    
    try:
        # IMPORTANTE: Ativar inserção manual de IDs (IDENTITY_INSERT)
        
        if n_barcos:
            cur.executemany("INSERT INTO barco (idbarco, nomebarco, tamanhobarco, paisbarco, tipobarco, capacidadeteu) VALUES (?, ?, ?, ?, ?, ?)", n_barcos)
            
        if n_conds:
            cur.executemany("INSERT INTO condutor (idcondutor, nomecondutor, idadecondutor, sexo, tipocertificado) VALUES (?, ?, ?, ?, ?)", n_conds)

        if n_locs:
            cur.executemany("INSERT INTO localizacaoorigem (idorigem, nomeporto, pais) VALUES (?, ?, ?)", n_locs)

        if n_tempos:
            cur.executemany("INSERT INTO tempo (idtempo, datacompleta, ano, semestre, mes, dia) VALUES (?, ?, ?, ?, ?, ?)", n_tempos)

        if n_tipos: 
            cur.executemany("INSERT INTO tipoviagem (idtipoviagem, descricaotipoviagem) VALUES (?, ?)", n_tipos)
        if n_empresas: 
            cur.executemany("INSERT INTO empresabarco (idempresabarco, nomeempresabarco, paisempresa, emailempresa) VALUES (?, ?, ?, ?)", n_empresas)

        # FACTOS
        if n_factos:
            cur.executemany("""
                INSERT INTO viagens (
                    receitataxas, numcontentores, teutotal, contagemviagens, numdias,
                    tempo_idtempo, localizacaoorigem_idorigem, tipoviagem_idtipoviagem,
                    empresabarco_idempresabarco, condutor_idcondutor, barco_idbarco
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, n_factos)
            
        conn.commit()
        print(f"Sucesso CSV: {len(n_factos)} viagens adicionadas.")

    except Exception as e:
        print(f"Erro SQL CSV: {e}")
        conn.rollback()
        
def execute_sql_script(conn, script_path):
    print(f"A executar script SQL extra: {script_path}...")
    cur = conn.cursor()
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
        #Separar por ;
        commands = sql_script.split(';')
        
        count = 0
        
        cur.execute("ALTER TABLE viagens NOCHECK CONSTRAINT ALL;")
        
        
        for command in commands:
            if command.strip(): # Ignorar linhas vazias
                try:
                    cur.execute(command)
                    count += 1
                except Exception as e:
                    print(f"Aviso: Erro no comando #{count}: {e}")
        
        conn.commit()
        print(f"Script executado com sucesso. {count} comandos processados.")
        
    except FileNotFoundError:
        print(f"ERRO: Ficheiro {script_path} não encontrado.")
    except Exception as e:
        print(f"ERRO CRÍTICO ao executar script SQL: {e}")
        cur.rollback()        

# Função Main
def main():
    try:
        print("1 - Ligação ao MySQL")
        conn_mysql = get_mysql_conn() 
        (barco, localizacao, empresas, condutores, tipos_viagem, lista_tempo, viagens_facto) = fetch_from_mysql(conn_mysql)
        print(f" Dados recolhidos: {len(barco)} barcos | {len(localizacao)} locais | {len(empresas)} empresas")
        print(f" {len(condutores)} condutores | {len(tipos_viagem)} tipos | {len(lista_tempo)} datas | {len(viagens_facto)} factos")
        conn_mysql.close() 
        print("Ligação MySQL fechada.")

        print("2 - Ligação ao MsSQL")
        mssql = get_mssql_conn() 
        
        erase_dw(mssql)  
        
        try:
            print("3 - Criação/Limpeza das tabelas staging")
            ensure_staging(mssql) 
            print("4 - Preenche as tabelas de staging")
            bulk_load_staging(mssql, barco, localizacao, empresas, condutores, tipos_viagem, lista_tempo, viagens_facto) 
            print("5 - Upsert das dimensões")
            insert_dimensions(mssql) 
            print("6 - Carga da tabela de factos")
            load_fact(mssql, full_reload=True) 
            print("\n7 - Carga do Ficheiro CSV")
            lookups = get_sql_lookups(mssql)
            
            # 8. Processar CSV, encontrando/criando novos IDs
            (nb, nc, nl, nt, ntip, ne, nf) = process_csv_incremental('dados.csv', lookups)
            
            # 9. Inserir os novos dados do CSV no DW
            load_csv_to_sql(mssql, nb, nc, nl, nt, ntip, ne, nf)
            
            #10. Inserir dados novos do Mokaroo
            execute_sql_script(mssql, 'scriptDadosMokaroo.txt')
            
            #11. Limpar Staging
            erase_stg(mssql)
            
            print(" ETL concluído com sucesso.")
        finally:
            mssql.close() 
            print("Ligação SQL Server fechada.")
            
    except pyodbc.Error as e:
        print(f"Erro SQL Server (pyodbc): {e}")
        sys.exit(1)
    except mysql.Error as e:
        print(f"Erro MySQL (connector): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()