-- =============================================================================
-- ORDR - Sales Orders Header
-- RDR1 - Sales Orders Lines
-- SAP B1 pattern: DocEntry internal PK, DocNum visible to user
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ORDR — Header
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.ORDR', 'U') IS NOT NULL DROP TABLE dbo.ORDR;

CREATE TABLE dbo.ORDR (
    -- Key
    DocEntry        INT             NOT NULL IDENTITY(1,1),
    DocNum          INT             NOT NULL,               -- user-visible number (sequential per series)
    DocType         CHAR(1)         NOT NULL DEFAULT 'I',   -- 'I'=stock

    -- Status
    DocStatus       CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=open, 'C'=closed
    CANCELED        CHAR(1)         NOT NULL DEFAULT 'N',   -- 'Y'=cancelled

    -- Partner
    CardCode        NVARCHAR(15)    NOT NULL,
    CardName        NVARCHAR(100)   NOT NULL,

    -- Dates
    DocDate         DATE            NOT NULL,               -- document date
    DocDueDate      DATE            NOT NULL,               -- promised delivery date
    TaxDate         DATE            NULL,                   -- fiscal posting date

    -- Default warehouse
    WhsCode         NVARCHAR(8)     NULL,

    -- Totals (local currency)
    DocTotal        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscSum         DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PaidToDate      DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Sales rep / payment terms
    SlpCode         SMALLINT        NULL,
    GroupNum        SMALLINT        NULL,                   -- payment terms

    -- Notes
    Comments        NVARCHAR(254)   NULL,

    -- Audit / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_ORDR      PRIMARY KEY (DocEntry),
    CONSTRAINT UQ_ORDR_Num  UNIQUE (DocNum),
    CONSTRAINT FK_ORDR_OCRD FOREIGN KEY (CardCode) REFERENCES dbo.OCRD (CardCode)
);

CREATE INDEX IX_ORDR_UpdateDate  ON dbo.ORDR (UpdateDate, UpdateTS);
CREATE INDEX IX_ORDR_CardCode    ON dbo.ORDR (CardCode);
CREATE INDEX IX_ORDR_DocStatus   ON dbo.ORDR (DocStatus, CANCELED);
CREATE INDEX IX_ORDR_DocDate     ON dbo.ORDR (DocDate);


-- ---------------------------------------------------------------------------
-- RDR1 — Lines
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.RDR1', 'U') IS NOT NULL DROP TABLE dbo.RDR1;

CREATE TABLE dbo.RDR1 (
    -- Composite key (header DocEntry + LineNum)
    DocEntry        INT             NOT NULL,
    LineNum         INT             NOT NULL,

    -- Item
    ItemCode        NVARCHAR(50)    NOT NULL,
    Dscription      NVARCHAR(100)   NOT NULL,
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    OpenQty         DECIMAL(19,6)   NOT NULL DEFAULT 0,     -- remaining qty to deliver

    -- Prices
    Price           DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PriceAfVAT      DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscPrcnt       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    LineTotal       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Warehouse and lot
    WhsCode         NVARCHAR(8)     NULL,
    BatchNum        NVARCHAR(50)    NULL,

    -- Line status
    LineStatus      CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=open, 'C'=closed

    -- Dates
    ShipDate        DATE            NULL,

    CONSTRAINT PK_RDR1      PRIMARY KEY (DocEntry, LineNum),
    CONSTRAINT FK_RDR1_ORDR FOREIGN KEY (DocEntry)  REFERENCES dbo.ORDR (DocEntry),
    CONSTRAINT FK_RDR1_OITM FOREIGN KEY (ItemCode)  REFERENCES dbo.OITM (ItemCode)
);

CREATE INDEX IX_RDR1_ItemCode ON dbo.RDR1 (ItemCode);
