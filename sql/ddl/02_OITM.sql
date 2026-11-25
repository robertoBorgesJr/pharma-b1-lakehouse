-- =============================================================================
-- OITM - Items Master Data (Cadastro de Itens)
-- SAP B1 pattern: ItemCode PK, campos farmacêuticos (EAN, regulatório)
-- =============================================================================
IF OBJECT_ID('dbo.OITM', 'U') IS NOT NULL DROP TABLE dbo.OITM;

CREATE TABLE dbo.OITM (
    -- Chave
    ItemCode        NVARCHAR(50)    NOT NULL,
    ItemName        NVARCHAR(100)   NOT NULL,
    FrgnName        NVARCHAR(100)   NULL,       -- nome técnico/comercial alternativo

    -- Classificação
    ItmsGrpCod      SMALLINT        NOT NULL DEFAULT 100,   -- grupo de itens
    ItemType        CHAR(1)         NOT NULL DEFAULT 'I',   -- 'I'=estoque, 'S'=serviço
    InvntItem       CHAR(1)         NOT NULL DEFAULT 'Y',   -- controla estoque
    SellItem        CHAR(1)         NOT NULL DEFAULT 'Y',
    PrcrmntMtd      CHAR(1)         NOT NULL DEFAULT 'B',   -- 'B'=compra, 'M'=fabricação

    -- Unidades
    SalUnitMsr      NVARCHAR(8)     NULL DEFAULT 'UN',
    PurUnitMsr      NVARCHAR(8)     NULL DEFAULT 'UN',
    InvntryUom      NVARCHAR(8)     NULL DEFAULT 'UN',

    -- Fiscal
    TaxCodeAR       NVARCHAR(20)    NULL,       -- NCM / grupo tributário saída
    TaxCodeAP       NVARCHAR(20)    NULL,

    -- Farmacêutico
    CodeBars        NVARCHAR(50)    NULL,       -- EAN-13
    RegNum          NVARCHAR(50)    NULL,       -- registro ANVISA
    ManBtchNum      CHAR(1)         NOT NULL DEFAULT 'Y',   -- controle por lote (crítico farma)
    MngMethod       CHAR(1)         NULL DEFAULT 'F',       -- 'F'=FEFO, 'B'=FIFO

    -- Preços
    LastPurPrc      DECIMAL(19,6)   NULL DEFAULT 0,
    AvgPrice        DECIMAL(19,6)   NULL DEFAULT 0,

    -- Status
    validFor        CHAR(1)         NOT NULL DEFAULT 'Y',
    frozenFor       CHAR(1)         NOT NULL DEFAULT 'N',

    -- Auditoria / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OITM PRIMARY KEY (ItemCode)
);

CREATE INDEX IX_OITM_UpdateDate ON dbo.OITM (UpdateDate, UpdateTS);
CREATE INDEX IX_OITM_ItmsGrpCod ON dbo.OITM (ItmsGrpCod);
