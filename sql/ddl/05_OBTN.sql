-- =============================================================================
-- OBTN - Batch Numbers (Lotes)
-- SAP B1 pattern: rastreabilidade e validade — crítico no setor farmacêutico
-- AbsEntry PK interna; BatchNum é o código visível (ex.: L2024001)
-- =============================================================================
IF OBJECT_ID('dbo.OBTN', 'U') IS NOT NULL DROP TABLE dbo.OBTN;

CREATE TABLE dbo.OBTN (
    -- Chave interna
    AbsEntry        INT             NOT NULL IDENTITY(1,1),

    -- Identificação do lote
    ItemCode        NVARCHAR(50)    NOT NULL,
    BatchNum        NVARCHAR(50)    NOT NULL,   -- número do lote (ex.: L2024001)
    WhsCode         NVARCHAR(8)     NULL,

    -- Farmacêutico
    MfgDate         DATE            NULL,       -- data de fabricação
    ExpDate         DATE            NULL,       -- data de validade — crítico farma/ANVISA
    AdmDate         DATE            NULL,       -- data de admissão no estoque

    -- Quantidade
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Status do lote
    -- 'A'=aprovado, 'Q'=quarentena, 'R'=reprovado, 'C'=consumido
    Status          NVARCHAR(1)     NOT NULL DEFAULT 'A',

    -- Rastreabilidade ANVISA (farmacêutico)
    LotNumber       NVARCHAR(50)    NULL,       -- número do lote do fornecedor
    SuppLotNum      NVARCHAR(50)    NULL,       -- lote interno vs. lote do fornecedor

    -- Notas
    Details         NVARCHAR(254)   NULL,

    -- Auditoria / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OBTN      PRIMARY KEY (AbsEntry),
    CONSTRAINT UQ_OBTN_Lot  UNIQUE (ItemCode, BatchNum, WhsCode),
    CONSTRAINT FK_OBTN_OITM FOREIGN KEY (ItemCode) REFERENCES dbo.OITM (ItemCode)
);

CREATE INDEX IX_OBTN_UpdateDate ON dbo.OBTN (UpdateDate, UpdateTS);
CREATE INDEX IX_OBTN_ItemCode   ON dbo.OBTN (ItemCode, BatchNum);
CREATE INDEX IX_OBTN_ExpDate    ON dbo.OBTN (ExpDate);   -- alertas de vencimento
