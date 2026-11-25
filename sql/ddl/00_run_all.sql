-- =============================================================================
-- 00_run_all.sql — Creates all MVP tables in the correct order
-- Target database: SBO_PHARMA_LAB
-- Run connected to the correct database:
--   sqlcmd -S sql-b1-lab-roberto.database.windows.net -d SBO_PHARMA_LAB -U b1admin -i 00_run_all.sql
-- =============================================================================
USE SBO_PHARMA_LAB;
GO

PRINT '1/7 OCRD - Business Partners';
:r 01_OCRD.sql
GO

PRINT '2/7 OITM - Item Master Data';
:r 02_OITM.sql
GO

PRINT '3/7 OWHS - Warehouses (before OITW due to FK)';
:r 03_OWHS.sql
GO

PRINT '4/7 OITW - Stock by Warehouse';
:r 04_OITW.sql
GO

PRINT '5/7 OBTN - Batch Numbers';
:r 05_OBTN.sql
GO

PRINT '6/7 ORDR + RDR1 - Sales Orders';
:r 06_ORDR_RDR1.sql
GO

PRINT '7/7 OINV + INV1 - AR Invoices';
:r 07_OINV_INV1.sql
GO

PRINT '=== MVP created successfully ===';
GO
