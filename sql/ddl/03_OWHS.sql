-- =============================================================================
-- OWHS - Warehouses
-- SAP B1 pattern: reference table; referenced by OITW
-- Created before OITW due to FK dependency
-- =============================================================================
IF OBJECT_ID('dbo.OWHS', 'U') IS NOT NULL DROP TABLE dbo.OWHS;

CREATE TABLE dbo.OWHS (
    WhsCode         NVARCHAR(8)     NOT NULL,
    WhsName         NVARCHAR(100)   NOT NULL,

    -- Location
    Street          NVARCHAR(100)   NULL,
    City            NVARCHAR(100)   NULL,
    State           NVARCHAR(3)     NULL,
    Country         NVARCHAR(3)     NULL DEFAULT 'BR',

    -- Pharmaceutical: warehouse type
    -- 'PA'=finished goods, 'MP'=raw material, 'QUA'=quarantine, 'DEV'=returns
    Location        NVARCHAR(10)    NULL,

    IsDropShip      CHAR(1)         NOT NULL DEFAULT 'N',
    Inactive        CHAR(1)         NOT NULL DEFAULT 'N',

    -- Audit
    UpdateDate      DATE            NOT NULL,
    UpdateTS        INT             NOT NULL DEFAULT 0,

    CONSTRAINT PK_OWHS PRIMARY KEY (WhsCode)
);
