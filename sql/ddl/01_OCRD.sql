-- =============================================================================
-- OCRD - Business Partners (Parceiros de Negócio)
-- SAP B1 pattern: CardCode PK, watermark por UpdateDate + UpdateTS
-- =============================================================================
IF OBJECT_ID('dbo.OCRD', 'U') IS NOT NULL DROP TABLE dbo.OCRD;

CREATE TABLE dbo.OCRD (
    -- Chave
    CardCode        NVARCHAR(15)    NOT NULL,   -- código único do parceiro (ex.: C00001, F00001)
    CardName        NVARCHAR(100)   NOT NULL,
    CardType        CHAR(1)         NOT NULL,   -- 'C'=Cliente, 'S'=Fornecedor, 'L'=Lead

    -- Dados fiscais
    LicTradNum      NVARCHAR(32)    NULL,       -- CNPJ/CPF
    TaxIdNum        NVARCHAR(32)    NULL,       -- inscrição estadual

    -- Endereço principal
    Address         NVARCHAR(100)   NULL,
    ZipCode         NVARCHAR(20)    NULL,
    City            NVARCHAR(100)   NULL,
    State           NVARCHAR(3)     NULL,
    Country         NVARCHAR(3)     NULL DEFAULT 'BR',

    -- Contato
    Phone1          NVARCHAR(20)    NULL,
    E_Mail          NVARCHAR(100)   NULL,

    -- Classificação
    GroupCode       SMALLINT        NULL,       -- grupo de parceiros
    SlpCode         SMALLINT        NULL,       -- código do representante

    -- Status
    validFor        CHAR(1)         NOT NULL DEFAULT 'Y',   -- 'Y'=ativo, 'N'=inativo
    frozenFor       CHAR(1)         NOT NULL DEFAULT 'N',   -- bloqueado

    -- Auditoria / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,     -- hora criação HHMMSS
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,     -- hora última atualização HHMMSS

    CONSTRAINT PK_OCRD PRIMARY KEY (CardCode)
);

CREATE INDEX IX_OCRD_UpdateDate ON dbo.OCRD (UpdateDate, UpdateTS);
CREATE INDEX IX_OCRD_CardType   ON dbo.OCRD (CardType);
