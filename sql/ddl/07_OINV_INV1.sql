-- =============================================================================
-- OINV - AR Invoices Header
-- INV1 - AR Invoices Lines
-- SAP B1 pattern: same as ORDR but represents an issued NF (fiscal document)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- OINV — Header
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.OINV', 'U') IS NOT NULL DROP TABLE dbo.OINV;

CREATE TABLE dbo.OINV (
    -- Key
    DocEntry        INT             NOT NULL IDENTITY(1,1),
    DocNum          INT             NOT NULL,
    DocType         CHAR(1)         NOT NULL DEFAULT 'I',

    -- Status — NF is only 'cancelled' ('Y') or 'closed' ('C'); never deleted
    DocStatus       CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=open, 'C'=closed/paid
    CANCELED        CHAR(1)         NOT NULL DEFAULT 'N',

    -- Partner
    CardCode        NVARCHAR(15)    NOT NULL,
    CardName        NVARCHAR(100)   NOT NULL,

    -- Traceability to source order
    BaseEntry       INT             NULL,                   -- DocEntry of the source ORDR

    -- Dates
    DocDate         DATE            NOT NULL,               -- issue date
    DocDueDate      DATE            NOT NULL,               -- due date
    TaxDate         DATE            NULL,

    -- NF-e Access Key (pharma: fiscal traceability)
    FolioNum        NVARCHAR(50)    NULL,                   -- invoice number
    Series          NVARCHAR(3)     NULL,                   -- invoice series
    ChaveNFe        NVARCHAR(44)    NULL,                   -- NF-e access key (44 digits)

    -- Warehouse
    WhsCode         NVARCHAR(8)     NULL,

    -- Totals
    DocTotal        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscSum         DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PaidToDate      DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Sales rep / payment terms
    SlpCode         SMALLINT        NULL,
    GroupNum        SMALLINT        NULL,

    Comments        NVARCHAR(254)   NULL,

    -- Audit / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OINV      PRIMARY KEY (DocEntry),
    CONSTRAINT UQ_OINV_Num  UNIQUE (DocNum),
    CONSTRAINT FK_OINV_OCRD FOREIGN KEY (CardCode)   REFERENCES dbo.OCRD (CardCode),
    CONSTRAINT FK_OINV_ORDR FOREIGN KEY (BaseEntry)  REFERENCES dbo.ORDR (DocEntry)
);

CREATE INDEX IX_OINV_UpdateDate ON dbo.OINV (UpdateDate, UpdateTS);
CREATE INDEX IX_OINV_CardCode   ON dbo.OINV (CardCode);
CREATE INDEX IX_OINV_DocStatus  ON dbo.OINV (DocStatus, CANCELED);
CREATE INDEX IX_OINV_DocDate    ON dbo.OINV (DocDate);
CREATE INDEX IX_OINV_BaseEntry  ON dbo.OINV (BaseEntry);


-- ---------------------------------------------------------------------------
-- INV1 — Lines
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.INV1', 'U') IS NOT NULL DROP TABLE dbo.INV1;

CREATE TABLE dbo.INV1 (
    DocEntry        INT             NOT NULL,
    LineNum         INT             NOT NULL,

    -- Item
    ItemCode        NVARCHAR(50)    NOT NULL,
    Dscription      NVARCHAR(100)   NOT NULL,
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Prices
    Price           DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PriceAfVAT      DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscPrcnt       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    LineTotal       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Warehouse and lot (traceability — critical pharma)
    WhsCode         NVARCHAR(8)     NULL,
    BatchNum        NVARCHAR(50)    NULL,

    -- Traceability to source order line
    BaseEntry       INT             NULL,
    BaseLine        INT             NULL,

    -- Fiscal
    TaxCode         NVARCHAR(20)    NULL,
    CFOPCode        NVARCHAR(5)     NULL,                   -- CFOP (Brazilian fiscal code)

    LineStatus      CHAR(1)         NOT NULL DEFAULT 'C',   -- NF lines are always closed

    CONSTRAINT PK_INV1      PRIMARY KEY (DocEntry, LineNum),
    CONSTRAINT FK_INV1_OINV FOREIGN KEY (DocEntry)  REFERENCES dbo.OINV (DocEntry),
    CONSTRAINT FK_INV1_OITM FOREIGN KEY (ItemCode)  REFERENCES dbo.OITM (ItemCode)
);

CREATE INDEX IX_INV1_ItemCode  ON dbo.INV1 (ItemCode);
CREATE INDEX IX_INV1_BatchNum  ON dbo.INV1 (BatchNum);     -- lot traceability
CREATE INDEX IX_INV1_BaseEntry ON dbo.INV1 (BaseEntry, BaseLine);
