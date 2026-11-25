#!/usr/bin/env python3
"""
simulate_activity.py — Simulador de atividade pontual para SBO_PHARMA_LAB.

Executa um "dia" de movimentações típicas de uma indústria farmacêutica.
Cada execução produz mudanças detectáveis pelo watermark (UpdateDate+UpdateTS):

  1. Novos pedidos de venda (ORDR/RDR1)
  2. Faturamento de pedidos abertos → NFs (OINV/INV1)
  3. Cancelamento de um pedido aberto
  4. Alteração de cadastro de parceiros e itens (bumpa UpdateDate+UpdateTS)
  5. Recebimento de novo lote (OBTN)
  6. Inativação pontual de cliente (validFor='N') — testa reconciliação de exclusões

Uso:
    python generator/simulate_activity.py
    python generator/simulate_activity.py --date 2026-11-25
    python generator/simulate_activity.py --orders 5
    python generator/simulate_activity.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyodbc
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

CFOP_INTRA = "5102"
CFOP_INTER = "6102"

_STREET_NAMES = ["Paulista", "Brasil", "das Nações", "do Comércio", "Industrial", "das Flores"]

# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------


def get_connection() -> pyodbc.Connection:
    server   = os.environ["B1_SQL_SERVER"]
    database = os.environ["B1_SQL_DATABASE"]
    user     = os.environ["B1_SQL_USER"]
    password = os.environ["B1_SQL_PASSWORD"]
    driver   = os.environ.get("B1_SQL_DRIVER", "ODBC Driver 18 for SQL Server")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str, autocommit=False)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def _ts_now() -> int:
    """Hora atual como inteiro HHMMSS."""
    n = datetime.now()
    return n.hour * 10_000 + n.minute * 100 + n.second


def _ts_rand(rng: random.Random) -> int:
    return rng.randint(7, 17) * 10_000 + rng.randint(0, 59) * 100 + rng.randint(0, 59)


def _nfe_chave(doc_date: date, seq_nf: str, rng: random.Random) -> str:
    """Chave NF-e fictícia de exatamente 44 dígitos."""
    return (
        "35"
        + doc_date.strftime("%y%m")
        + "".join(str(rng.randint(0, 9)) for _ in range(14))
        + "55"
        + "001"
        + seq_nf
        + "1"
        + "".join(str(rng.randint(0, 9)) for _ in range(8))
        + str(rng.randint(0, 9))
    )


# ---------------------------------------------------------------------------
# Leitura do estado atual do banco
# ---------------------------------------------------------------------------


@dataclass
class _Client:
    card_code: str
    card_name: str
    state: str
    slp_code: int
    group_num: int


@dataclass
class _ItemLot:
    item_code: str
    item_name: str
    tax_code: str | None
    batch_num: str
    whs_code: str


@dataclass
class _OrderLine:
    line_num: int
    item_code: str
    dscription: str
    quantity: float
    price: float
    price_af_vat: float
    disc_prcnt: float
    line_total: float
    vat_sum: float
    whs_code: str
    batch_num: str | None


@dataclass
class _OpenOrder:
    doc_entry: int
    doc_num: int
    card_code: str
    card_name: str
    state: str
    doc_date: date
    doc_due_date: date
    doc_total: float
    vat_sum: float
    slp_code: int
    group_num: int
    lines: list[_OrderLine] = field(default_factory=list)


def _fetch_clients(cur: pyodbc.Cursor) -> list[_Client]:
    cur.execute("""
        SELECT TOP 60 CardCode, CardName, State,
               ISNULL(SlpCode, 1), ISNULL(GroupCode, 1)
        FROM dbo.OCRD
        WHERE validFor = 'Y' AND CardType = 'C'
        ORDER BY NEWID()
    """)
    return [_Client(*row) for row in cur.fetchall()]


def _fetch_items_with_lots(cur: pyodbc.Cursor, sim_date: date) -> list[_ItemLot]:
    cur.execute("""
        SELECT o.ItemCode, o.ItemName, o.TaxCodeAR,
               b.BatchNum,
               CASE WHEN o.ItemCode IN ('INSUR','ERTP004') THEN 'PA02' ELSE 'PA01' END
        FROM dbo.OITM o
        JOIN dbo.OBTN b ON b.ItemCode = o.ItemCode
        WHERE o.SellItem = 'Y' AND o.validFor = 'Y'
          AND b.Status = 'A'
          AND b.ExpDate > ?
    """, sim_date)
    return [_ItemLot(*row) for row in cur.fetchall()]


def _fetch_open_orders(cur: pyodbc.Cursor) -> list[_OpenOrder]:
    cur.execute("""
        SELECT o.DocEntry, o.DocNum,
               o.CardCode, o.CardName,
               ISNULL(c.State, 'SP'),
               o.DocDate, o.DocDueDate,
               o.DocTotal, o.VatSum,
               ISNULL(o.SlpCode, 1), ISNULL(o.GroupNum, 1)
        FROM dbo.ORDR o
        LEFT JOIN dbo.OCRD c ON c.CardCode = o.CardCode
        WHERE o.DocStatus = 'O' AND o.CANCELED = 'N'
        ORDER BY o.DocDate ASC
    """)
    orders = [_OpenOrder(*row) for row in cur.fetchall()]

    for order in orders:
        cur.execute("""
            SELECT LineNum, ItemCode, Dscription,
                   Quantity, Price, PriceAfVAT, DiscPrcnt,
                   LineTotal, VatSum, WhsCode, BatchNum
            FROM dbo.RDR1
            WHERE DocEntry = ?
        """, order.doc_entry)
        order.lines = [_OrderLine(*row) for row in cur.fetchall()]

    return orders


def _next_doc_num(cur: pyodbc.Cursor, table: str) -> int:
    cur.execute(f"SELECT ISNULL(MAX(DocNum), 0) + 1 FROM dbo.{table}")
    return cur.fetchone()[0]


def _next_batch_seq(cur: pyodbc.Cursor, item_code: str, ym: str) -> int:
    """Maior sequência de lote do mês para o item, +1."""
    prefix = f"L{ym}{item_code[:4].upper()}"
    cur.execute(
        "SELECT ISNULL(MAX(CAST(RIGHT(BatchNum, 3) AS INT)), 0) + 1 "
        "FROM dbo.OBTN WHERE ItemCode = ? AND BatchNum LIKE ?",
        item_code, prefix + "%",
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Ação 1 — Novos pedidos
# ---------------------------------------------------------------------------


def _make_order_lines(
    rng: random.Random,
    items: list[_ItemLot],
    n_lines: int,
) -> tuple[list[_OrderLine], float, float]:
    """Retorna (linhas, doc_total, vat_total)."""
    chosen: list[_ItemLot] = rng.sample(items, min(n_lines, len(items)))
    # Deduplica por ItemCode mantendo a primeira ocorrência
    seen: set[str] = set()
    deduped: list[_ItemLot] = []
    for il in chosen:
        if il.item_code not in seen:
            seen.add(il.item_code)
            deduped.append(il)

    lines: list[_OrderLine] = []
    doc_total = Decimal("0")
    vat_total = Decimal("0")

    for ln, il in enumerate(deduped):
        qty      = Decimal(str(round(rng.uniform(20, 400), 0)))
        price    = Decimal(str(round(rng.uniform(20, 800), 2)))
        disc_pct = Decimal(str(rng.choice([0, 0, 0, 2, 5, 10])))
        price_net = price * (1 - disc_pct / 100)
        vat_rate  = Decimal("0.12")
        line_net  = qty * price_net
        line_vat  = line_net * vat_rate

        doc_total += line_net
        vat_total += line_vat

        lines.append(_OrderLine(
            line_num    = ln,
            item_code   = il.item_code,
            dscription  = il.item_name,
            quantity    = float(qty),
            price       = float(price),
            price_af_vat= float(price_net * (1 + vat_rate)),
            disc_prcnt  = float(disc_pct),
            line_total  = float(line_net),
            vat_sum     = float(line_vat),
            whs_code    = il.whs_code,
            batch_num   = il.batch_num,
        ))

    return lines, float(doc_total), float(vat_total)


def insert_new_orders(
    conn: pyodbc.Connection,
    rng: random.Random,
    clients: list[_Client],
    items: list[_ItemLot],
    sim_date: date,
    n_orders: int,
    start_num: int,
) -> int:
    """Insere n_orders pedidos. Retorna próximo DocNum livre."""
    if not clients or not items:
        log.warning("Sem clientes ou itens disponíveis — pedidos ignorados.")
        return start_num

    sql_hdr = """
        INSERT INTO dbo.ORDR
            (DocNum, DocType, DocStatus, CANCELED, CardCode, CardName,
             DocDate, DocDueDate, TaxDate, WhsCode,
             DocTotal, VatSum, DiscSum, PaidToDate,
             SlpCode, GroupNum, Comments,
             CreateDate, CreateTS, UpdateDate, UpdateTS)
        OUTPUT INSERTED.DocEntry, INSERTED.DocNum
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    sql_line = """
        INSERT INTO dbo.RDR1
            (DocEntry, LineNum, ItemCode, Dscription, Quantity, OpenQty,
             Price, PriceAfVAT, DiscPrcnt, LineTotal, VatSum,
             WhsCode, BatchNum, LineStatus, ShipDate)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    ts = _ts_now()
    next_num = start_num

    with conn.cursor() as cur:
        for _ in range(n_orders):
            client     = rng.choice(clients)
            n_lines    = rng.randint(1, 5)
            lines, doc_total, vat_total = _make_order_lines(rng, items, n_lines)
            due_date   = sim_date + timedelta(days=rng.randint(7, 30))

            cur.execute(sql_hdr, (
                next_num, "I", "O", "N",
                client.card_code, client.card_name,
                sim_date, due_date, sim_date, "PA01",
                doc_total, vat_total, 0.0, 0.0,
                client.slp_code, client.group_num, None,
                sim_date, ts, sim_date, ts,
            ))
            doc_entry = cur.fetchone()[0]

            for ln in lines:
                cur.execute(sql_line, (
                    doc_entry, ln.line_num, ln.item_code, ln.dscription,
                    ln.quantity, ln.quantity,
                    ln.price, ln.price_af_vat, ln.disc_prcnt,
                    ln.line_total, ln.vat_sum,
                    ln.whs_code, ln.batch_num, "O", due_date,
                ))
            log.info("  ORDR DocNum=%d CardCode=%s Total=%.2f", next_num, client.card_code, doc_total)
            next_num += 1

    conn.commit()
    log.info("Novos pedidos: %d inseridos.", n_orders)
    return next_num


# ---------------------------------------------------------------------------
# Ação 2 — Faturar pedidos abertos
# ---------------------------------------------------------------------------


def invoice_open_orders(
    conn: pyodbc.Connection,
    rng: random.Random,
    open_orders: list[_OpenOrder],
    sim_date: date,
    start_inv_num: int,
    max_to_invoice: int = 5,
) -> int:
    """Cria OINV+INV1 para até max_to_invoice pedidos abertos. Retorna próximo DocNum."""
    if not open_orders:
        log.info("Sem pedidos abertos para faturar.")
        return start_inv_num

    to_invoice = rng.sample(open_orders, min(max_to_invoice, len(open_orders)))
    sql_hdr = """
        INSERT INTO dbo.OINV
            (DocNum, DocType, DocStatus, CANCELED, CardCode, CardName,
             BaseEntry, DocDate, DocDueDate, TaxDate,
             FolioNum, Series, ChaveNFe, WhsCode,
             DocTotal, VatSum, DiscSum, PaidToDate,
             SlpCode, GroupNum, Comments,
             CreateDate, CreateTS, UpdateDate, UpdateTS)
        OUTPUT INSERTED.DocEntry, INSERTED.DocNum
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    sql_inv_line = """
        INSERT INTO dbo.INV1
            (DocEntry, LineNum, ItemCode, Dscription, Quantity,
             Price, PriceAfVAT, DiscPrcnt, LineTotal, VatSum,
             WhsCode, BatchNum, BaseEntry, BaseLine,
             TaxCode, CFOPCode, LineStatus)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    sql_close_order = """
        UPDATE dbo.ORDR
        SET DocStatus='C', PaidToDate=DocTotal, UpdateDate=?, UpdateTS=?
        WHERE DocEntry=?
    """
    ts   = _ts_now()
    nnum = start_inv_num

    with conn.cursor() as cur:
        for order in to_invoice:
            if not order.lines:
                continue
            inv_due  = sim_date + timedelta(days=rng.randint(28, 60))
            seq_nf   = str(nnum).zfill(9)
            cfop     = CFOP_INTRA if order.state == "SP" else CFOP_INTER

            cur.execute(sql_hdr, (
                nnum, "I", "C", "N",
                order.card_code, order.card_name,
                order.doc_entry,
                sim_date, inv_due, sim_date,
                seq_nf, "001", _nfe_chave(sim_date, seq_nf, rng), "PA01",
                order.doc_total, order.vat_sum, 0.0, order.doc_total,
                order.slp_code, order.group_num, None,
                sim_date, ts, sim_date, ts,
            ))
            inv_entry = cur.fetchone()[0]

            for ln in order.lines:
                cur.execute(sql_inv_line, (
                    inv_entry, ln.line_num, ln.item_code, ln.dscription,
                    ln.quantity,
                    ln.price, ln.price_af_vat, ln.disc_prcnt,
                    ln.line_total, ln.vat_sum,
                    ln.whs_code, ln.batch_num,
                    order.doc_entry, ln.line_num,
                    None, cfop, "C",
                ))

            cur.execute(sql_close_order, sim_date, ts, order.doc_entry)
            log.info(
                "  OINV DocNum=%d ← ORDR DocEntry=%d CardCode=%s",
                nnum, order.doc_entry, order.card_code,
            )
            nnum += 1

    conn.commit()
    log.info("Pedidos faturados: %d NFs emitidas.", len(to_invoice))
    return nnum


# ---------------------------------------------------------------------------
# Ação 3 — Cancelar pedido
# ---------------------------------------------------------------------------


def cancel_order(
    conn: pyodbc.Connection,
    open_orders: list[_OpenOrder],
    sim_date: date,
) -> None:
    if not open_orders:
        log.info("Sem pedidos abertos para cancelar.")
        return

    # Escolhe o mais antigo (vencido) ou aleatório
    target = min(open_orders, key=lambda o: o.doc_due_date)
    ts = _ts_now()

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE dbo.ORDR
            SET CANCELED='Y', DocStatus='C', UpdateDate=?, UpdateTS=?
            WHERE DocEntry=?
        """, sim_date, ts, target.doc_entry)
        cur.execute("""
            UPDATE dbo.RDR1
            SET LineStatus='C', OpenQty=0
            WHERE DocEntry=?
        """, target.doc_entry)

    conn.commit()
    log.info(
        "Pedido cancelado: ORDR DocNum=%d DocEntry=%d (vencimento: %s).",
        target.doc_num, target.doc_entry, target.doc_due_date,
    )


# ---------------------------------------------------------------------------
# Ação 4 — Alterações de cadastro (bumpa watermark)
# ---------------------------------------------------------------------------


def update_masters(
    conn: pyodbc.Connection,
    rng: random.Random,
    sim_date: date,
    n_clients: int = 3,
) -> None:
    ts = _ts_now()

    with conn.cursor() as cur:
        # Pega n_clients clientes aleatórios para atualizar
        cur.execute(f"""
            SELECT TOP {n_clients} CardCode
            FROM dbo.OCRD
            WHERE validFor='Y' AND CardType='C'
            ORDER BY NEWID()
        """)
        client_codes = [row[0] for row in cur.fetchall()]

        for code in client_codes:
            new_phone = f"({rng.randint(11,99)}) 9{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"
            new_addr  = f"Av. {rng.choice(_STREET_NAMES)} {rng.randint(100, 9999)}"
            cur.execute("""
                UPDATE dbo.OCRD
                SET Phone1=?, Address=?, UpdateDate=?, UpdateTS=?
                WHERE CardCode=?
            """, new_phone, new_addr, sim_date, ts, code)
            log.info("  OCRD atualizado: CardCode=%s", code)

        # Atualiza preço médio de 1-2 itens
        cur.execute("""
            SELECT TOP 2 ItemCode, AvgPrice
            FROM dbo.OITM
            WHERE validFor='Y' AND SellItem='Y'
            ORDER BY NEWID()
        """)
        items = cur.fetchall()
        for item_code, avg_price in items:
            delta      = Decimal(str(avg_price)) * Decimal(str(round(rng.uniform(-0.08, 0.12), 4)))
            new_price  = float(max(Decimal("0.01"), Decimal(str(avg_price)) + delta))
            cur.execute("""
                UPDATE dbo.OITM
                SET AvgPrice=?, LastPurPrc=?, UpdateDate=?, UpdateTS=?
                WHERE ItemCode=?
            """, round(new_price, 6), round(new_price, 6), sim_date, ts, item_code)
            log.info("  OITM atualizado: ItemCode=%s novo AvgPrice=%.4f", item_code, new_price)

    conn.commit()
    log.info("Cadastros atualizados: %d clientes, %d itens.", len(client_codes), len(items))


# ---------------------------------------------------------------------------
# Ação 5 — Novo lote recebido
# ---------------------------------------------------------------------------


def insert_new_lot(
    conn: pyodbc.Connection,
    rng: random.Random,
    sim_date: date,
    n_lots: int = 2,
) -> None:
    ts = _ts_now()
    ym = sim_date.strftime("%Y%m")

    with conn.cursor() as cur:
        # Escolhe itens para receber lote (prioritiza os que têm poucos lotes ativos)
        cur.execute("""
            SELECT TOP 5 o.ItemCode, o.ItemName,
                   CASE WHEN o.ItemCode IN ('INSUR','ERTP004') THEN 'PA02' ELSE 'PA01' END
            FROM dbo.OITM o
            WHERE o.PrcrmntMtd = 'M' AND o.validFor = 'Y'
            ORDER BY (
                SELECT COUNT(*) FROM dbo.OBTN b
                WHERE b.ItemCode = o.ItemCode AND b.Status = 'A'
            ) ASC, NEWID()
        """)
        candidates = cur.fetchall()

        inserted = 0
        for item_code, item_name, whs_code in candidates[:n_lots]:
            seq       = _next_batch_seq(cur, item_code, ym)
            batch_num = f"L{ym}{item_code[:4].upper()}{seq:03d}"
            shelf_map = {i[0]: i[8] for i in [
                ("AMOX500",36),("AZIT500",24),("CEFA500",36),("PARA750",48),
                ("DIPI500",48),("IBUP600",36),("DICL050",36),("LOSA050",48),
                ("ATEN025",48),("SINV020",36),("ANLO005",48),("METF850",48),
                ("GLIB005",48),("SALB100",24),("BUDE200",24),("VITC001",36),
                ("VITD003",24),("CXBVIT",36),("INSUR",18),("ERTP004",12),
            ]}
            shelf     = shelf_map.get(item_code, 36)
            mfg_date  = sim_date - timedelta(days=rng.randint(1, 10))
            exp_date  = mfg_date + timedelta(days=shelf * 30)
            adm_date  = sim_date
            qty       = round(rng.uniform(3000, 12000), 0)

            cur.execute("""
                INSERT INTO dbo.OBTN
                    (ItemCode, BatchNum, WhsCode, MfgDate, ExpDate, AdmDate,
                     Quantity, Status, LotNumber, SuppLotNum, Details,
                     CreateDate, CreateTS, UpdateDate, UpdateTS)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                item_code, batch_num, whs_code, mfg_date, exp_date, adm_date,
                qty, "A",
                f"FORN{rng.randint(100000, 999999)}", batch_num, None,
                adm_date, ts, adm_date, ts,
            )
            log.info(
                "  OBTN novo lote: %s ItemCode=%s ExpDate=%s Qty=%.0f",
                batch_num, item_code, exp_date, qty,
            )
            inserted += 1

    conn.commit()
    log.info("Novos lotes recebidos: %d.", inserted)


# ---------------------------------------------------------------------------
# Ação 6 — Inativar cliente (testa reconciliação de exclusões no lake)
# ---------------------------------------------------------------------------


def maybe_inactivate_client(
    conn: pyodbc.Connection,
    rng: random.Random,
    sim_date: date,
    probability: float = 0.15,
) -> None:
    if rng.random() > probability:
        return

    ts = _ts_now()
    with conn.cursor() as cur:
        # Escolhe cliente sem pedidos abertos nos últimos 60 dias
        cur.execute("""
            SELECT TOP 1 CardCode, CardName
            FROM dbo.OCRD
            WHERE validFor = 'Y' AND CardType = 'C'
              AND CardCode NOT IN (
                  SELECT DISTINCT CardCode FROM dbo.ORDR
                  WHERE DocDate >= ? AND DocStatus = 'O' AND CANCELED = 'N'
              )
            ORDER BY NEWID()
        """, sim_date - timedelta(days=60))
        row = cur.fetchone()
        if row is None:
            return
        card_code, card_name = row

        cur.execute("""
            UPDATE dbo.OCRD
            SET validFor='N', UpdateDate=?, UpdateTS=?
            WHERE CardCode=?
        """, sim_date, ts, card_code)

    conn.commit()
    log.info(
        "Cliente inativado (validFor='N'): CardCode=%s — testa reconciliação no lake.",
        card_code,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de atividade SBO_PHARMA_LAB")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Data de simulação (YYYY-MM-DD, padrão: hoje)",
    )
    parser.add_argument(
        "--orders",
        type=int,
        default=3,
        help="Número de novos pedidos a criar (padrão: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lê o estado do banco mas não grava nada",
    )
    args = parser.parse_args()

    sim_date = date.fromisoformat(args.date)
    rng      = random.Random()  # sem seed — resultado diferente a cada execução

    log.info("Simulando atividade para %s (--orders=%d).", sim_date, args.orders)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            clients     = _fetch_clients(cur)
            items       = _fetch_items_with_lots(cur, sim_date)
            open_orders = _fetch_open_orders(cur)
            next_order  = _next_doc_num(cur, "ORDR")
            next_inv    = _next_doc_num(cur, "OINV")

        log.info(
            "Estado atual: %d clientes ativos, %d item/lote combos, "
            "%d pedidos abertos. Próximos DocNum: ORDR=%d OINV=%d.",
            len(clients), len(items), len(open_orders), next_order, next_inv,
        )

        if not clients:
            log.error("Nenhum cliente ativo encontrado. Execute historical_load.py primeiro.")
            return
        if not items:
            log.error("Nenhum item com lote ativo. Execute historical_load.py primeiro.")
            return

        if args.dry_run:
            log.info("--dry-run: nenhuma gravação realizada.")
            return

        log.info("--- 1/6  Novos pedidos ---")
        insert_new_orders(conn, rng, clients, items, sim_date, args.orders, next_order)

        log.info("--- 2/6  Faturamento ---")
        invoice_open_orders(conn, rng, open_orders, sim_date, next_inv)

        log.info("--- 3/6  Cancelamento ---")
        cancel_order(conn, open_orders, sim_date)

        log.info("--- 4/6  Alterações de cadastro ---")
        update_masters(conn, rng, sim_date)

        log.info("--- 5/6  Recebimento de lote ---")
        insert_new_lot(conn, rng, sim_date)

        log.info("--- 6/6  Inativação de cliente (probabilística) ---")
        maybe_inactivate_client(conn, rng, sim_date)

        log.info("Simulação concluída para %s.", sim_date)
    finally:
        conn.close()
        log.info("Conexão fechada.")


if __name__ == "__main__":
    main()
