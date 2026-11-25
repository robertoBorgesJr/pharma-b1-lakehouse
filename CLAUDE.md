# CLAUDE.md — SAP Business One → Azure Databricks Lab

## Project context

Personal portfolio lab that simulates the integration of a **SAP Business One (B1) ERP** from a
**fictional pharmaceutical manufacturer** with a **lakehouse on Azure Databricks** (Medallion + dimensional modeling).

Goal: demonstrate end-to-end incremental extraction from a SQL Server database with B1 structure,
CDC, bronze/silver/gold layers, orchestration, and CI/CD — the same design that would be applied in a real environment.

> Public project (GitHub). **Do not mention real company names** in code, data, commits, or documentation.
> All data is synthetic.

Author: Roberto Borges (data engineer — SQL, Python, PySpark, Delta Lake, Unity Catalog, Terraform, DAB).
Local development on **Windows 11 + VS Code + Claude Code**, machine with **8 GB RAM** (avoid heavy local stacks).

---

## Provisioned environment

| Item | Value |
|---|---|
| Cloud | Azure (pay-as-you-go subscription) |
| Resource group | `rg-sap-b1-lab` |
| Logical server | `sql-b1-lab-roberto.database.windows.net` |
| Database | `SBO_PHARMA_LAB` (Azure SQL Database — free offer) |
| Tier | General Purpose, **Serverless**, 32 GB max. |
| Authentication | SQL + Microsoft Entra; SQL login `b1admin` |
| Network | Public endpoint with firewall: client IP + "Allow Azure services" (acceptable for lab only) |

### Free offer limits (always respect)
- 100,000 vCore-seconds/month (~28 h of 1 vCore), 32 GB data; resets every month.
- Configured to **auto-pause on limit reached** (no charge).
- The database only pauses **without active connections**. Therefore:
  - jobs must **connect, read/write, and disconnect** — no persistent connections;
  - **do not** leave simulators running in a loop;
  - the Lakeflow Connect gateway (managed CDC) stays connected 24/7 and exhausts the quota in ~1 day:
    use **only for a point-in-time test** and delete the gateway the same day.

### Secrets
- **Never** commit passwords, connection strings, or tokens.
- Local: `.env` file (in `.gitignore`), with `.env.example` versioned without values.
- Databricks: secret scope (e.g. `b1-lab`) or Unity Catalog connection.

---

## Target architecture

```
Azure SQL (SAP B1 structure)
   │  watermark CDC (UpdateDate + UpdateTS) — JDBC, serverless
   ▼
BRONZE  (append, metadata _ingested_at, _batch_id, _source)
   │  incremental by ingestion (Structured Streaming + checkpoint, trigger availableNow)
   ▼
SILVER  (typed, deduped, English business names, MERGE, expectations; Change Data Feed enabled)
   │  Change Data Feed → MERGE
   ▼
GOLD    (dimensional model: facts + conformed dimensions, SCD2 on master data)
```

### Decisions already made
1. **Compute:** serverless by default (short hourly jobs, no idle cost).
   Classic compute only when: managed CDC gateway requires it, network/IP restrictions,
   dependencies not supported in serverless (JARs, init scripts), or long historical load
   in a sized **job cluster** (ephemeral — destroyed at the end).
2. **Initial historical load:** in batches by period, saves the last watermark at the end;
   from then on the same incremental code runs in serverless every hour.
3. **Source CDC → bronze:** watermark by `UpdateDate` + `UpdateTS`, with an **overlap window**
   (re-read current and previous day when there is no `UpdateTS`); MERGE resolves duplicates.
4. **Deletions:** fiscal documents in B1 are cancelled (`CANCELED = 'Y'`) or closed (`DocStatus = 'C'`),
   not deleted → captured by watermark. Master data and drafts can be deleted →
   **periodic key reconciliation** (mark as deleted in the lake).
5. **Header + lines:** filter by header (e.g. OINV) and fetch lines (INV1) by `DocEntry`.
6. **Bronze → silver:** incremental by **ingestion date**, not by source date.
7. **Silver → gold:** Change Data Feed; discard `update_preimage`, deduplicate by key using the highest
   `_commit_version`, handle `delete`; for aggregates, recalculate only the affected keys.
8. **Optional evolution:** Change Tracking / native SQL Server CDC + Lakeflow Connect
   (compare with watermark; point-in-time test due to quota).
9. **Term "watermark"** in this project = incremental load control, **not** Structured Streaming's `withWatermark`.

---

## Source data model (simulated B1 structure)

Table/column names follow the SAP B1 standard (validate details against SAP documentation when possible).

| Area | Tables |
|---|---|
| Master data | `OCRD` (business partners), `OITM` (items), `OITW` (stock by warehouse), `OWHS` (warehouses) |
| Sales | `ORDR`/`RDR1` (sales orders), `OINV`/`INV1` (outbound invoices), `ORIN`/`RIN1` (returns) |
| Purchasing | `OPOR`/`POR1` (purchase orders), `OPDN`/`PDN1` (goods receipt), `OPCH`/`PCH1` (vendor invoice) |
| Finance | `OJDT`/`JDT1` (journal entries), `OACT` (chart of accounts), `OOCR` (cost centers) |
| Production/MRP | `OWOR`/`WOR1` (production orders), `OITT`/`ITT1` (bill of materials) |
| Quality/Lots | `OBTN` (lots — traceability and expiry are critical in the pharma sector) |
| Audit history | `ACRD`, `AITM`, `ADOC`/`ADO1` (change log, `LogInstanc`) — basis for SCD2 and auditing |

Required control columns in simulated tables: `DocEntry` (internal document PK),
`CreateDate`, `UpdateDate` (date only), `UpdateTS`/`CreateTS` (time as integer HHMMSS),
`CANCELED`, `DocStatus`.

**MVP scope:** `OCRD`, `OITM`, `OITW`, `ORDR`/`RDR1`, `OINV`/`INV1`, `OBTN`.
Remaining tables are added in later phases.

---

## Lakehouse (Databricks / Unity Catalog)

- Separate catalogs: `pharma_lakehouse_dev` and `pharma_lakehouse_prod`; schemas `bronze_sap_b1`, `silver_sap_b1`, `gold_sap_b1`, `control`.
- Control table: `control.watermark_pipelines` (one record per pipeline/table/layer, updated via MERGE).
- Silver with English business names (e.g. `OINV` → `sales_invoice`) and `delta.enableChangeDataFeed = true`
  from creation (CDF is not retroactive).
- Gold (MVP):
  - Facts: `fact_sales` (grain: invoice line), `fact_inventory_snapshot`
  - Dimensions: `dim_customer` (SCD2), `dim_product` (SCD2), `dim_lot`, `dim_warehouse`, `dim_date`
- Future phase: integrate Salesforce (Account/Opportunity/Product2) with `dim_customer` unified by **CNPJ**.
- Governance: column masks / row filters for personal data (LGPD compliance) where applicable.

---

## Suggested repository structure

```
pharma-b1-lakehouse/
├── CLAUDE.md
├── README.md                  # overview, diagram, "how it would work in production"
├── .env.example
├── sql/
│   ├── ddl/                   # CREATE TABLE in B1 pattern
│   └── cdc/                   # scripts to enable Change Tracking/CDC (optional phase)
├── generator/                 # Python + pyodbc (ODBC Driver 18 for SQL Server)
│   ├── historical_load.py     # historical load (e.g. 2 years)
│   └── simulate_activity.py   # one-shot run: new orders, invoicing, cancellations, updates
├── src/
│   └── b1_lakehouse/          # Python package (pyproject.toml), reusable utilities
│       ├── utils/             # connections.py, environment.py, watermark_control.py
│       ├── bronze/
│       ├── silver/
│       └── gold/
├── resources/                 # Databricks Asset Bundle job definitions
├── databricks.yml             # DAB: targets dev/prod; serverless default, job_cluster for historical load
├── infra/                     # Terraform (Unity Catalog, schemas, permissions)
└── .github/workflows/         # CI/CD (validate/deploy bundle)
```

---

## Code conventions

- Python with type hints; small testable functions; structured logging (no `print`).
- Generator SQL: batch inserts, explicit transactions, close connection at the end.
- PySpark: avoid `collect()` on large data; idempotent MERGE; safe for reprocessing.
- English names for business objects (silver/gold); original B1 names in bronze.
- Small, descriptive commits.
- Whenever an architectural decision arises, record it in `README.md` (section "Decisions").

---

## Roadmap

1. [ ] DDL for MVP tables in `SBO_PHARMA_LAB`
2. [ ] Historical data generator (pharma-flavored data: lots, expiry dates, warehouses)
3. [ ] Activity simulator (insert/update/cancel/delete of master records)
4. [ ] Bronze: JDBC extraction by watermark (serverless) + control table
5. [ ] Silver: streaming with checkpoint + MERGE + expectations + CDF
6. [ ] Gold: facts and dimensions (SCD2) via CDF
7. [ ] Deletion reconciliation (master data)
8. [ ] DAB + GitHub Actions (dev/prod); hourly chained job bronze → silver → gold
9. [ ] Observability: failure alerts, pipeline health dashboard
10. [ ] (Optional) Change Tracking/native CDC + Lakeflow Connect point-in-time test
11. [ ] (Future) Salesforce source and unified `dim_customer` by CNPJ

---

## How Claude should work in this project

- Before suggesting anything that runs against the database, consider the **vCore-second quota consumption**.
- For claims about Databricks features, prefer the official documentation (docs.databricks.com)
  and explicitly state when something has not been confirmed.
- Do not rewrite entire files without necessity; propose incremental changes.
- When completing a roadmap step, check off the item above.
