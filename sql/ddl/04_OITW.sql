-- =============================================================================
-- OITW - Items by Warehouse (Stock by Warehouse)
-- SAP B1 pattern: composite PK (ItemCode, WhsCode), no DocEntry
-- No native UpdateTS in B1 — updated via trigger or generator logic
-- =============================================================================
IF OBJECT_ID('dbo.OITW', 'U') IS NOT NULL DROP TABLE dbo.OITW;

CREATE TABLE dbo.OITW (
    -- Composite key
    ItemCode        NVARCHAR(50)    NOT NULL,
    WhsCode         NVARCHAR(8)     NOT NULL,

    -- Stock balances
    OnHand          DECIMAL(19,6)   NOT NULL DEFAULT 0,     -- on-hand stock
    IsCommited      DECIMAL(19,6)   NOT NULL DEFAULT 0,     -- committed (open orders)
    OnOrder         DECIMAL(19,6)   NOT NULL DEFAULT 0,     -- on purchase order
    Available       AS (OnHand - IsCommited),               -- available (computed column)

    -- Min/max stock levels
    MinLevel        DECIMAL(19,6)   NULL DEFAULT 0,
    MaxLevel        DECIMAL(19,6)   NULL DEFAULT 0,

    -- Audit / watermark (no UpdateTS — only date available in real B1)
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OITW PRIMARY KEY (ItemCode, WhsCode),
    CONSTRAINT FK_OITW_OITM FOREIGN KEY (ItemCode) REFERENCES dbo.OITM (ItemCode),
    CONSTRAINT FK_OITW_OWHS FOREIGN KEY (WhsCode)  REFERENCES dbo.OWHS (WhsCode)
);

CREATE INDEX IX_OITW_UpdateDate ON dbo.OITW (UpdateDate, UpdateTS);
