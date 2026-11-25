-- =============================================================================
-- OCRD - Business Partners
-- SAP B1 pattern: CardCode PK, watermark by UpdateDate + UpdateTS
-- =============================================================================
IF OBJECT_ID('dbo.OCRD', 'U') IS NOT NULL DROP TABLE dbo.OCRD;

CREATE TABLE dbo.OCRD (
    -- Key
    CardCode        NVARCHAR(15)    NOT NULL,   -- unique partner code (e.g. C00001, F00001)
    CardName        NVARCHAR(100)   NOT NULL,
    CardType        CHAR(1)         NOT NULL,   -- 'C'=Customer, 'S'=Supplier, 'L'=Lead

    -- Fiscal data
    LicTradNum      NVARCHAR(32)    NULL,       -- CNPJ/CPF
    TaxIdNum        NVARCHAR(32)    NULL,       -- state tax registration

    -- Primary address
    Address         NVARCHAR(100)   NULL,
    ZipCode         NVARCHAR(20)    NULL,
    City            NVARCHAR(100)   NULL,
    State           NVARCHAR(3)     NULL,
    Country         NVARCHAR(3)     NULL DEFAULT 'BR',

    -- Contact
    Phone1          NVARCHAR(20)    NULL,
    E_Mail          NVARCHAR(100)   NULL,

    -- Classification
    GroupCode       SMALLINT        NULL,       -- partner group
    SlpCode         SMALLINT        NULL,       -- sales rep code

    -- Status
    validFor        CHAR(1)         NOT NULL DEFAULT 'Y',   -- 'Y'=active, 'N'=inactive
    frozenFor       CHAR(1)         NOT NULL DEFAULT 'N',   -- blocked/frozen

    -- Audit / watermark
    CreateDate      DATE            NOT NULL,
    CreateTS        INT             NOT NULL DEFAULT 0,     -- creation time HHMMSS
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,     -- last update time HHMMSS

    CONSTRAINT PK_OCRD PRIMARY KEY (CardCode)
);

CREATE INDEX IX_OCRD_UpdateDate ON dbo.OCRD (UpdateDate, UpdateTS);
CREATE INDEX IX_OCRD_CardType   ON dbo.OCRD (CardType);
