-- =============================================================================
-- OITM - Items Master Data
-- SAP B1 pattern: ItemCode PK, pharma fields (EAN, regulatory)
-- =============================================================================
IF OBJECT_ID('dbo.OITM', 'U') IS NOT NULL DROP TABLE dbo.OITM;

CREATE TABLE dbo.OITM (
    -- Key
    ItemCode        NVARCHAR(50)    NOT NULL,
    ItemName        NVARCHAR(100)   NOT NULL,
    FrgnName        NVARCHAR(100)   NULL,       -- alternative technical/commercial name

    -- Classification
    ItmsGrpCod      SMALLINT        NOT NULL DEFAULT 100,   -- item group
    ItemType        CHAR(1)         NOT NULL DEFAULT 'I',   -- 'I'=stock, 'S'=service
    InvntItem       CHAR(1)         NOT NULL DEFAULT 'Y',   -- stock control
    SellItem        CHAR(1)         NOT NULL DEFAULT 'Y',
    PrcrmntMtd      CHAR(1)         NOT NULL DEFAULT 'B',   -- 'B'=purchase, 'M'=manufacture

    -- Units
    SalUnitMsr      NVARCHAR(8)     NULL DEFAULT 'UN',
    PurUnitMsr      NVARCHAR(8)     NULL DEFAULT 'UN',
    InvntryUom      NVARCHAR(8)     NULL DEFAULT 'UN',

    -- Fiscal
    TaxCodeAR       NVARCHAR(20)    NULL,       -- NCM / outbound tax group
    TaxCodeAP       NVARCHAR(20)    NULL,

    -- Pharmaceutical
    CodeBars        NVARCHAR(50)    NULL,       -- EAN-13
    RegNum          NVARCHAR(50)    NULL,       -- ANVISA registration
    ManBtchNum      CHAR(1)         NOT NULL DEFAULT 'Y',   -- lot control (critical for pharma)
    MngMethod       CHAR(1)         NULL DEFAULT 'F',       -- 'F'=FEFO, 'B'=FIFO

    -- Prices
    LastPurPrc      DECIMAL(19,6)   NULL DEFAULT 0,
    AvgPrice        DECIMAL(19,6)   NULL DEFAULT 0,

    -- Status
    validFor        CHAR(1)         NOT NULL DEFAULT 'Y',
    frozenFor       CHAR(1)         NOT NULL DEFAULT 'N',

    -- Audit / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OITM PRIMARY KEY (ItemCode)
);

CREATE INDEX IX_OITM_UpdateDate ON dbo.OITM (UpdateDate, UpdateTS);
CREATE INDEX IX_OITM_ItmsGrpCod ON dbo.OITM (ItmsGrpCod);
