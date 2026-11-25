-- =============================================================================
-- OBTN - Batch Numbers (Lots)
-- SAP B1 pattern: traceability and expiry — critical in the pharma sector
-- AbsEntry internal PK; BatchNum is the visible code (e.g. L2024001)
-- =============================================================================
IF OBJECT_ID('dbo.OBTN', 'U') IS NOT NULL DROP TABLE dbo.OBTN;

CREATE TABLE dbo.OBTN (
    -- Internal key
    AbsEntry        INT             NOT NULL IDENTITY(1,1),

    -- Lot identification
    ItemCode        NVARCHAR(50)    NOT NULL,
    BatchNum        NVARCHAR(50)    NOT NULL,   -- lot number (e.g. L2024001)
    WhsCode         NVARCHAR(8)     NULL,

    -- Pharmaceutical
    MfgDate         DATE            NULL,       -- manufacturing date
    ExpDate         DATE            NULL,       -- expiry date — critical pharma/ANVISA
    AdmDate         DATE            NULL,       -- admission date into stock

    -- Quantity
    Quantity        DECIMAL(19,6)   NOT NULL DEFAULT 0,

    -- Lot status
    -- 'A'=approved, 'Q'=quarantine, 'R'=rejected, 'C'=consumed
    Status          NVARCHAR(1)     NOT NULL DEFAULT 'A',

    -- ANVISA traceability (pharmaceutical)
    LotNumber       NVARCHAR(50)    NULL,       -- supplier lot number
    SuppLotNum      NVARCHAR(50)    NULL,       -- internal lot vs. supplier lot

    -- Notes
    Details         NVARCHAR(254)   NULL,

    -- Audit / watermark
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
CREATE INDEX IX_OBTN_ExpDate    ON dbo.OBTN (ExpDate);   -- expiry alerts
