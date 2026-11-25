-- =============================================================================
-- OINV - AR Invoices Header (Cabeçalho de Notas Fiscais de Saída)
-- INV1 - AR Invoices Lines  (Linhas de Notas Fiscais de Saída)
-- SAP B1 pattern: igual a ORDR mas representa NF emitida (documento fiscal)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- OINV — Cabeçalho
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.OINV', 'U') IS NOT NULL DROP TABLE dbo.OINV;

CREATE TABLE dbo.OINV (
    -- Chave
    DocEntry        INT             NOT NULL IDENTITY(1,1),
    DocNum          INT             NOT NULL,
    DocType         CHAR(1)         NOT NULL DEFAULT 'I',

    -- Status — NF só é "cancelada" ('Y') ou "fechada" ('C'); nunca apagada
    DocStatus       CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=aberto, 'C'=fechado/pago
    CANCELED        CHAR(1)         NOT NULL DEFAULT 'N',

    -- Parceiro
    CardCode        NVARCHAR(15)    NOT NULL,
    CardName        NVARCHAR(100)   NOT NULL,

    -- Rastreabilidade com o pedido de origem
    BaseEntry       INT             NULL,                   -- DocEntry da ORDR de origem

    -- Datas
    DocDate         DATE            NOT NULL,               -- data de emissão
    DocDueDate      DATE            NOT NULL,               -- data de vencimento
    TaxDate         DATE            NULL,

    -- Chave de Acesso NF-e (farmacêutico: rastreabilidade fiscal)
    FolioNum        NVARCHAR(50)    NULL,                   -- número da NF
    Series          NVARCHAR(3)     NULL,                   -- série da NF
    ChaveNFe        NVARCHAR(44)    NULL,                   -- chave de acesso NF-e (44 dígitos)

    -- Depósito
    WhsCode         NVARCHAR(8)     NULL,

    -- Totais
    DocTotal        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscSum         DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PaidToDate      DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Representante / condição
    SlpCode         SMALLINT        NULL,
    GroupNum        SMALLINT        NULL,

    Comments        NVARCHAR(254)   NULL,

    -- Auditoria / watermark
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
-- INV1 — Linhas
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.INV1', 'U') IS NOT NULL DROP TABLE dbo.INV1;

CREATE TABLE dbo.INV1 (
    DocEntry        INT             NOT NULL,
    LineNum         INT             NOT NULL,

    -- Item
    ItemCode        NVARCHAR(50)    NOT NULL,
    Dscription      NVARCHAR(100)   NOT NULL,
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Preços
    Price           DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PriceAfVAT      DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscPrcnt       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    LineTotal       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Depósito e lote (rastreabilidade — crítico farma)
    WhsCode         NVARCHAR(8)     NULL,
    BatchNum        NVARCHAR(50)    NULL,

    -- Rastreabilidade com linha do pedido de origem
    BaseEntry       INT             NULL,
    BaseLine        INT             NULL,

    -- Fiscal
    TaxCode         NVARCHAR(20)    NULL,
    CFOPCode        NVARCHAR(5)     NULL,                   -- CFOP (fiscal Brasil)

    LineStatus      CHAR(1)         NOT NULL DEFAULT 'C',   -- linhas de NF sempre fechadas

    CONSTRAINT PK_INV1      PRIMARY KEY (DocEntry, LineNum),
    CONSTRAINT FK_INV1_OINV FOREIGN KEY (DocEntry)  REFERENCES dbo.OINV (DocEntry),
    CONSTRAINT FK_INV1_OITM FOREIGN KEY (ItemCode)  REFERENCES dbo.OITM (ItemCode)
);

CREATE INDEX IX_INV1_ItemCode  ON dbo.INV1 (ItemCode);
CREATE INDEX IX_INV1_BatchNum  ON dbo.INV1 (BatchNum);     -- rastreabilidade por lote
CREATE INDEX IX_INV1_BaseEntry ON dbo.INV1 (BaseEntry, BaseLine);
