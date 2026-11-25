# CLAUDE.md — Laboratório SAP Business One → Azure Databricks

## Contexto do projeto

Laboratório pessoal de portfólio que simula a integração de um **ERP SAP Business One (B1)** de uma
**indústria farmacêutica fictícia** com um **lakehouse no Azure Databricks** (Medallion + modelagem dimensional).

Objetivo: demonstrar, de ponta a ponta, extração incremental de um banco SQL Server com estrutura de B1,
CDC, camadas bronze/silver/gold, orquestração e CI/CD — o mesmo desenho que seria aplicado em um ambiente real.

> Projeto público (GitHub). **Não citar nomes de empresas reais** em código, dados, commits ou documentação.
> Todos os dados são sintéticos.

Autor: Roberto Borges (engenheiro de dados — SQL, Python, PySpark, Delta Lake, Unity Catalog, Terraform, DAB).
Desenvolvimento local em **Windows 11 + VS Code + Claude Code**, máquina com **8 GB de RAM** (evitar stacks pesadas locais).

---

## Ambiente já provisionado

| Item | Valor |
|---|---|
| Cloud | Azure (assinatura pay-as-you-go) |
| Resource group | `rg-sap-b1-lab` |
| Servidor lógico | `sql-b1-lab-roberto.database.windows.net` |
| Banco | `SBO_PHARMA_LAB` (Azure SQL Database — oferta gratuita) |
| Tier | General Purpose, **Serverless**, 32 GB máx. |
| Autenticação | SQL + Microsoft Entra; login SQL `b1admin` |
| Rede | Endpoint público com firewall: IP do cliente + "Allow Azure services" (aceitável só para lab) |

### Limites da oferta gratuita (respeitar sempre)
- 100.000 vCore-segundos/mês (~28 h de 1 vCore), 32 GB de dados; renova todo mês.
- Configurado para **auto-pause ao atingir o limite** (sem cobrança).
- O banco só pausa **sem conexões ativas**. Portanto:
  - jobs devem **conectar, ler/escrever e desconectar** — nada de conexões persistentes;
  - **não** deixar simuladores rodando em loop;
  - o gateway do Lakeflow Connect (CDC gerenciado) fica conectado 24/7 e consome a cota em ~1 dia:
    usar **só em teste pontual** e excluir o gateway no mesmo dia.

### Segredos
- **Nunca** commitar senhas, connection strings ou tokens.
- Local: arquivo `.env` (no `.gitignore`), com `.env.example` versionado sem valores.
- Databricks: secret scope (ex.: `b1-lab`) ou conexão do Unity Catalog.

---

## Arquitetura alvo

```
Azure SQL (estrutura SAP B1)
   │  CDC por watermark (UpdateDate + UpdateTS) — JDBC, serverless
   ▼
BRONZE  (append, metadados _ingested_at, _batch_id, _source)
   │  incremental por ingestão (Structured Streaming + checkpoint, trigger availableNow)
   ▼
SILVER  (tipagem, dedup, nomes de negócio, MERGE, expectations; Change Data Feed habilitado)
   │  Change Data Feed → MERGE
   ▼
GOLD    (modelo dimensional: fatos + dimensões conformadas, SCD2 em cadastros)
```

### Decisões já tomadas
1. **Compute:** serverless por padrão (jobs horários curtos, sem custo ocioso).
   Compute clássico só quando: o gateway do CDC gerenciado exigir, restrições de rede/IP,
   dependências não suportadas no serverless (JARs, init scripts), ou carga histórica longa
   em **job cluster** dimensionado (efêmero — destruído ao final).
2. **Carga histórica inicial:** em lotes por período, grava o último watermark ao final;
   a partir daí o mesmo código incremental roda em serverless de hora em hora.
3. **CDC origem → bronze:** watermark por `UpdateDate` + `UpdateTS`, com **janela de sobreposição**
   (reler dia atual e anterior quando não houver `UpdateTS`); MERGE resolve duplicidades.
4. **Exclusões:** documentos fiscais no B1 são cancelados (`CANCELED = 'Y'`) ou fechados (`DocStatus = 'C'`),
   não apagados → capturados pelo watermark. Cadastros e rascunhos podem ser apagados →
   **reconciliação periódica de chaves** (marcar como excluído no lake).
5. **Cabeçalho + linhas:** filtrar pelo cabeçalho (ex.: OINV) e trazer as linhas (INV1) pelo `DocEntry`.
6. **Bronze → silver:** incremental pela **data de ingestão**, não pela data da origem.
7. **Silver → gold:** Change Data Feed; descartar `update_preimage`, deduplicar por chave pela maior
   `_commit_version`, tratar `delete`; em agregados, recalcular só as chaves afetadas.
8. **Evolução opcional:** Change Tracking / CDC nativo do SQL Server + Lakeflow Connect
   (comparar com o watermark; teste pontual por causa da cota).
9. **Termo "watermark"** neste projeto = controle de carga incremental, **não** o `withWatermark`
   do Structured Streaming.

---

## Modelo de dados de origem (estrutura B1 simulada)

Nomes de tabelas/colunas seguem o padrão SAP B1 (validar detalhes contra a documentação SAP quando possível).

| Área | Tabelas |
|---|---|
| Mestres | `OCRD` (parceiros), `OITM` (itens), `OITW` (estoque por depósito), `OWHS` (depósitos) |
| Comercial | `ORDR`/`RDR1` (pedidos de venda), `OINV`/`INV1` (NF saída), `ORIN`/`RIN1` (devoluções) |
| Compras | `OPOR`/`POR1` (pedidos de compra), `OPDN`/`PDN1` (recebimento), `OPCH`/`PCH1` (NF entrada) |
| Financeiro | `OJDT`/`JDT1` (lançamentos), `OACT` (plano de contas), `OOCR` (centros de custo) |
| Produção/PCP | `OWOR`/`WOR1` (ordens de produção), `OITT`/`ITT1` (estrutura de produto) |
| Qualidade/Lotes | `OBTN` (lotes — rastreabilidade e validade são críticas no setor farmacêutico) |
| Histórico | `ACRD`, `AITM`, `ADOC`/`ADO1` (log de alterações, `LogInstanc`) — base para SCD2 e auditoria |

Colunas de controle obrigatórias nas tabelas simuladas: `DocEntry` (PK interna de documentos),
`CreateDate`, `UpdateDate` (só data), `UpdateTS`/`CreateTS` (hora como inteiro HHMMSS),
`CANCELED`, `DocStatus`.

**Escopo do MVP:** `OCRD`, `OITM`, `OITW`, `ORDR`/`RDR1`, `OINV`/`INV1`, `OBTN`.
Demais tabelas entram em fases seguintes.

---

## Lakehouse (Databricks / Unity Catalog)

- Catálogos separados: `b1_lab_dev` e `b1_lab_prd`; schemas `bronze`, `silver`, `gold`, `controle`.
- Tabela de controle: `controle.watermark_pipelines` (um registro por pipeline/tabela/camada, atualizada via MERGE).
- Silver com nomes de negócio (ex.: `OINV` → `nota_fiscal_saida`) e `delta.enableChangeDataFeed = true`
  desde a criação (CDF não é retroativo).
- Gold (MVP):
  - Fatos: `fato_vendas` (grão: linha de NF), `fato_estoque_snapshot`
  - Dimensões: `dim_cliente` (SCD2), `dim_produto` (SCD2), `dim_lote`, `dim_deposito`, `dim_tempo`
- Fase futura: integrar Salesforce (Account/Opportunity/Product2) com de-para por **CNPJ** na `dim_cliente`.
- Governança: column masks / row filters para dados pessoais (LGPD) quando houver.

---

## Estrutura sugerida do repositório

```
pharma-b1-lakehouse/
├── CLAUDE.md
├── README.md                  # visão geral, diagrama, "como seria em produção"
├── .env.example
├── sql/
│   ├── ddl/                   # CREATE TABLE no padrão B1
│   └── cdc/                   # scripts para habilitar Change Tracking/CDC (fase opcional)
├── generator/                 # Python + pyodbc (ODBC Driver 18 for SQL Server)
│   ├── historical_load.py     # carga histórica (ex.: 2 anos)
│   └── simulate_activity.py   # execução pontual: novos pedidos, faturamento, cancelamentos, alterações
├── src/
│   └── b1_lakehouse/          # pacote Python (pyproject.toml), utils reaproveitáveis
│       ├── utils/             # connections.py, environment.py, watermark_control.py
│       ├── bronze/
│       ├── silver/
│       └── gold/
├── resources/                 # definições de jobs do Databricks Asset Bundle
├── databricks.yml             # DAB: targets dev/prd; serverless padrão, job_cluster para carga histórica
├── infra/                     # Terraform (Unity Catalog, schemas, permissões)
└── .github/workflows/         # CI/CD (validate/deploy do bundle)
```

---

## Convenções de código

- Python com type hints; funções pequenas e testáveis; logging estruturado (sem `print`).
- SQL do gerador: inserções em lote, transações explícitas, fechar conexão ao final.
- PySpark: evitar `collect()` em dados grandes; MERGE idempotente; reprocessamento seguro.
- Nomes em português para objetos de negócio (silver/gold); nomes originais do B1 na bronze.
- Commits pequenos e descritivos.
- Sempre que surgir uma decisão de arquitetura, registrar em `README.md` (seção "Decisões").

---

## Roadmap

1. [ ] DDL das tabelas do MVP no `SBO_PHARMA_LAB`
2. [ ] Gerador da carga histórica (dados com cara de farma: lotes, validade, depósitos)
3. [ ] Simulador de atividade (insert/update/cancelamento/exclusão de cadastro)
4. [ ] Bronze: extração JDBC por watermark (serverless) + tabela de controle
5. [ ] Silver: streaming com checkpoint + MERGE + expectations + CDF
6. [ ] Gold: fatos e dimensões (SCD2) via CDF
7. [ ] Reconciliação de exclusões (cadastros)
8. [ ] DAB + GitHub Actions (dev/prd); job horário encadeado bronze → silver → gold
9. [ ] Observabilidade: alertas de falha, dashboard de saúde dos pipelines
10. [ ] (Opcional) Change Tracking/CDC nativo + teste pontual do Lakeflow Connect
11. [ ] (Futuro) Origem Salesforce e `dim_cliente` unificada por CNPJ

---

## Como o Claude deve trabalhar neste projeto

- Antes de sugerir algo que rode no banco, considerar o **consumo da cota de vCore-segundos**.
- Para afirmações sobre recursos do Databricks, preferir a documentação oficial (docs.databricks.com)
  e dizer explicitamente quando algo não foi confirmado.
- Não reescrever arquivos inteiros sem necessidade; propor mudanças incrementais.
- Ao concluir uma etapa do roadmap, marcar o item acima.
