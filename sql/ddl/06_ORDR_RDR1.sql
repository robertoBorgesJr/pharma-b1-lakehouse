-- =============================================================================
-- ORDR - Sales Orders Header (Cabeçalho de Pedidos de Venda)
-- RDR1 - Sales Orders Lines  (Linhas de Pedidos de Venda)
-- SAP B1 pattern: DocEntry PK interna, DocNum visível ao usuário
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ORDR — Cabeçalho
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.ORDR', 'U') IS NOT NULL DROP TABLE dbo.ORDR;

CREATE TABLE dbo.ORDR (
    -- Chave
    DocEntry        INT             NOT NULL IDENTITY(1,1),
    DocNum          INT             NOT NULL,               -- número visível (sequencial por série)
    DocType         CHAR(1)         NOT NULL DEFAULT 'I',   -- 'I'=estoque

    -- Status
    DocStatus       CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=aberto, 'C'=fechado
    CANCELED        CHAR(1)         NOT NULL DEFAULT 'N',   -- 'Y'=cancelado

    -- Parceiro
    CardCode        NVARCHAR(15)    NOT NULL,
    CardName        NVARCHAR(100)   NOT NULL,

    -- Datas
    DocDate         DATE            NOT NULL,               -- data do documento
    DocDueDate      DATE            NOT NULL,               -- data de entrega prometida
    TaxDate         DATE            NULL,                   -- data de competência fiscal

    -- Depósito padrão
    WhsCode         NVARCHAR(8)     NULL,

    -- Totais (moeda local)
    DocTotal        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscSum         DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PaidToDate      DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Representante / condição de pagamento
    SlpCode         SMALLINT        NULL,
    GroupNum        SMALLINT        NULL,                   -- condição de pagamento

    -- Observações
    Comments        NVARCHAR(254)   NULL,

    -- Auditoria / watermark
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
-- RDR1 — Linhas
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.RDR1', 'U') IS NOT NULL DROP TABLE dbo.RDR1;

CREATE TABLE dbo.RDR1 (
    -- Chave composta (DocEntry do cabeçalho + LineNum)
    DocEntry        INT             NOT NULL,
    LineNum         INT             NOT NULL,

    -- Item
    ItemCode        NVARCHAR(50)    NOT NULL,
    Dscription      NVARCHAR(100)   NOT NULL,
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,
    OpenQty         DECIMAL(19,6)   NOT NULL DEFAULT 0,     -- saldo a entregar

    -- Preços
    Price           DECIMAL(19,6)   NOT NULL DEFAULT 0,
    PriceAfVAT      DECIMAL(19,6)   NOT NULL DEFAULT 0,
    DiscPrcnt       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    LineTotal       DECIMAL(19,6)   NOT NULL DEFAULT 0,
    VatSum          DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Depósito e lote
    WhsCode         NVARCHAR(8)     NULL,
    BatchNum        NVARCHAR(50)    NULL,

    -- Status da linha
    LineStatus      CHAR(1)         NOT NULL DEFAULT 'O',   -- 'O'=aberta, 'C'=fechada

    -- Datas
    ShipDate        DATE            NULL,

    CONSTRAINT PK_RDR1      PRIMARY KEY (DocEntry, LineNum),
    CONSTRAINT FK_RDR1_ORDR FOREIGN KEY (DocEntry)  REFERENCES dbo.ORDR (DocEntry),
    CONSTRAINT FK_RDR1_OITM FOREIGN KEY (ItemCode)  REFERENCES dbo.OITM (ItemCode)
);

CREATE INDEX IX_RDR1_ItemCode ON dbo.RDR1 (ItemCode);
