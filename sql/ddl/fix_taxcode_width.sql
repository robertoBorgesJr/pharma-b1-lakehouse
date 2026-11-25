-- Widens TaxCode columns from NVARCHAR(8) to NVARCHAR(20)
-- Required because NCM values (e.g. 'NCM300410') are 9 characters long.
-- Run once on the existing database; no DROP/CREATE.

ALTER TABLE dbo.OITM ALTER COLUMN TaxCodeAR NVARCHAR(20) NULL;
ALTER TABLE dbo.OITM ALTER COLUMN TaxCodeAP NVARCHAR(20) NULL;
ALTER TABLE dbo.INV1  ALTER COLUMN TaxCode   NVARCHAR(20) NULL;
