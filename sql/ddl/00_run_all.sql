-- =============================================================================
-- 00_run_all.sql — Cria todas as tabelas do MVP em ordem correta
-- Banco alvo: SBO_PHARMA_LAB
-- Executar conectado ao banco correto:
--   sqlcmd -S sql-b1-lab-roberto.database.windows.net -d SBO_PHARMA_LAB -U b1admin -i 00_run_all.sql
-- =============================================================================
USE SBO_PHARMA_LAB;
GO

PRINT '1/7 OCRD - Parceiros de negócio';
:r 01_OCRD.sql
GO

PRINT '2/7 OITM - Cadastro de itens';
:r 02_OITM.sql
GO

PRINT '3/7 OWHS - Depósitos (antes de OITW por FK)';
:r 03_OWHS.sql
GO

PRINT '4/7 OITW - Estoque por depósito';
:r 04_OITW.sql
GO

PRINT '5/7 OBTN - Lotes';
:r 05_OBTN.sql
GO

PRINT '6/7 ORDR + RDR1 - Pedidos de venda';
:r 06_ORDR_RDR1.sql
GO

PRINT '7/7 OINV + INV1 - Notas fiscais de saída';
:r 07_OINV_INV1.sql
GO

PRINT '=== MVP criado com sucesso ===';
GO
