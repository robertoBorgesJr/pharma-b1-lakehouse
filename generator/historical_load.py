#!/usr/bin/env python3
"""
historical_load.py — Carga histórica de ~2 anos para o banco SBO_PHARMA_LAB.

Gera dados sintéticos com cara de indústria farmacêutica (lotes, validade,
sazonalidade, rastreabilidade fiscal) e os insere em lote no Azure SQL,
respeitando as restrições de cota: conectar → inserir → desconectar.

Uso:
    python generator/historical_load.py
    python generator/historical_load.py --reset      # limpa as tabelas antes
    python generator/historical_load.py --dry-run    # só exibe volumes, não conecta
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyodbc
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

SEED = 42
BATCH_SIZE = 500

START_DATE = date(2024, 11, 1)
END_DATE   = date(2026, 11, 24)

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
# Utilitários de tempo
# ---------------------------------------------------------------------------


def ts_from_hms(h: int, m: int, s: int) -> int:
    """Converte hora/minuto/segundo no inteiro HHMMSS do B1."""
    return h * 10_000 + m * 100 + s


def rand_ts(rng: random.Random) -> int:
    return ts_from_hms(rng.randint(7, 17), rng.randint(0, 59), rng.randint(0, 59))


# ---------------------------------------------------------------------------
# Catálogos de referência
# ---------------------------------------------------------------------------

WAREHOUSES: list[dict[str, Any]] = [
    {"WhsCode": "PA01", "WhsName": "Produto Acabado — Principal",   "Location": "PA",  "City": "São Paulo", "State": "SP"},
    {"WhsCode": "PA02", "WhsName": "Produto Acabado — Câmara Fria", "Location": "PA",  "City": "São Paulo", "State": "SP"},
    {"WhsCode": "MP01", "WhsName": "Matéria-Prima",                 "Location": "MP",  "City": "São Paulo", "State": "SP"},
    {"WhsCode": "QUA",  "WhsName": "Quarentena",                    "Location": "QUA", "City": "São Paulo", "State": "SP"},
    {"WhsCode": "DEV",  "WhsName": "Devoluções",                    "Location": "DEV", "City": "São Paulo", "State": "SP"},
]

# (ItemCode, ItemName, FrgnName, ItmsGrpCod, TaxCode, RegANVISA, MngMethod, PrcrmntMtd, shelf_months)
_ITEMS_CATALOG: list[tuple[str, str, str, int, str | None, str | None, str, str, int]] = [
    # Antibióticos (100)
    ("AMOX500",  "Amoxicilina 500mg Caps",          "Amoxicillin 500mg",         100, "NCM300410", "1234567890001-9", "F", "M", 36),
    ("AZIT500",  "Azitromicina 500mg Comp",          "Azithromycin 500mg",        100, "NCM300410", "1234567890002-7", "F", "M", 24),
    ("CEFA500",  "Cefalexina 500mg Caps",            "Cephalexin 500mg",          100, "NCM300410", "1234567890003-5", "F", "M", 36),
    # Analgésicos/Antipiréticos (101)
    ("PARA750",  "Paracetamol 750mg Comp",           "Paracetamol 750mg",         101, "NCM300490", "1234567890004-3", "F", "M", 48),
    ("DIPI500",  "Dipirona Sódica 500mg Comp",       "Dipyrone 500mg",            101, "NCM300490", "1234567890005-1", "F", "M", 48),
    # Anti-inflamatórios (102)
    ("IBUP600",  "Ibuprofeno 600mg Comp Rev",        "Ibuprofen 600mg",           102, "NCM300490", "1234567890007-8", "F", "M", 36),
    ("DICL050",  "Diclofenaco Sódico 50mg Comp",     "Diclofenac Na 50mg",        102, "NCM300490", "1234567890008-6", "F", "M", 36),
    # Cardiovascular / Metabólico (103)
    ("LOSA050",  "Losartana Potássica 50mg Comp",    "Losartan K 50mg",           103, "NCM300490", "1234567890009-4", "F", "M", 48),
    ("ATEN025",  "Atenolol 25mg Comp",               "Atenolol 25mg",             103, "NCM300490", "1234567890010-8", "F", "M", 48),
    ("SINV020",  "Sinvastatina 20mg Comp",           "Simvastatin 20mg",          103, "NCM300490", "1234567890011-6", "F", "M", 36),
    ("ANLO005",  "Anlodipino 5mg Comp",              "Amlodipine 5mg",            103, "NCM300490", "1234567890012-4", "F", "M", 48),
    ("METF850",  "Metformina 850mg Comp",            "Metformin 850mg",           103, "NCM300490", "1234567890013-2", "F", "M", 48),
    ("GLIB005",  "Glibenclamida 5mg Comp",           "Glibenclamide 5mg",         103, "NCM300490", "1234567890014-0", "F", "M", 48),
    # Respiratório (104)
    ("SALB100",  "Salbutamol 100mcg Spray",          "Salbutamol 100mcg Inhaler", 104, "NCM300490", "1234567890015-9", "F", "M", 24),
    ("BUDE200",  "Budesonida 200mcg Spray",          "Budesonide 200mcg Inhaler", 104, "NCM300490", "1234567890016-7", "F", "M", 24),
    # Vitaminas/Suplementos (105)
    ("VITC001",  "Vitamina C 1g Efervescente",       "Vitamin C 1g",              105, "NCM300450", "1234567890017-5", "F", "M", 36),
    ("VITD003",  "Vitamina D3 2000UI Caps",          "Vitamin D3 2000IU",         105, "NCM300450", "1234567890018-3", "F", "M", 24),
    ("CXBVIT",   "Complexo B 60 Comp",               "Vitamin B Complex",         105, "NCM300450", "1234567890019-1", "F", "M", 36),
    # Termolábeis → câmara fria PA02 (103 reutilizado por grupo)
    ("INSUR",    "Insulina Regular 100UI/mL Fr",     "Insulin Regular 100IU/mL",  103, "NCM300431", "1234567890020-5", "F", "M", 18),
    ("ERTP004",  "Eritropoetina 4000UI/mL Fr",       "Erythropoietin 4000IU/mL",  103, "NCM300431", "1234567890021-3", "F", "M", 12),
    # Matéria-prima (200) — PrcrmntMtd='B', não são vendidos
    ("MP-AMOX",  "Amoxicilina Trihidratada - MP",    "Amoxicillin Trihydrate USP",200, None, None, "F", "B", 24),
    ("MP-PARA",  "Paracetamol - MP",                 "Paracetamol USP",           200, None, None, "F", "B", 36),
    ("MP-IBUP",  "Ibuprofeno - MP",                  "Ibuprofen USP",             200, None, None, "F", "B", 36),
    ("MP-LOSA",  "Losartana Potássica - MP",         "Losartan Potassium USP",    200, None, None, "F", "B", 48),
]

SELLABLE_CODES: list[str]   = [i[0] for i in _ITEMS_CATALOG if i[7] == "M"]
COLD_CHAIN_CODES: set[str]  = {"INSUR", "ERTP004"}
ITEM_SHELF_MONTHS: dict[str, int] = {i[0]: i[8] for i in _ITEMS_CATALOG}

# Pesos de popularidade de venda (antibióticos e crônicos vendem mais)
_ITEM_WEIGHTS: dict[str, float] = {
    "PARA750": 3.0, "DIPI500": 2.5, "AMOX500": 2.5, "IBUP600": 2.0,
    "LOSA050": 2.5, "METF850": 2.5, "ATEN025": 2.0, "SINV020": 2.0,
    "VITC001": 1.5, "VITD003": 1.5,
}
ITEM_WEIGHTS: list[float] = [_ITEM_WEIGHTS.get(c, 1.0) for c in SELLABLE_CODES]

_STATES = ["SP", "RJ", "MG", "RS", "PR", "BA", "SC", "CE", "PE", "GO"]
_CITIES: dict[str, list[str]] = {
    "SP": ["São Paulo", "Campinas", "Ribeirão Preto", "Santo André", "Sorocaba"],
    "RJ": ["Rio de Janeiro", "Niterói", "Petrópolis"],
    "MG": ["Belo Horizonte", "Uberlândia", "Contagem"],
    "RS": ["Porto Alegre", "Caxias do Sul", "Canoas"],
    "PR": ["Curitiba", "Londrina", "Maringá"],
    "BA": ["Salvador", "Feira de Santana"],
    "SC": ["Florianópolis", "Blumenau", "Joinville"],
    "CE": ["Fortaleza", "Juazeiro do Norte"],
    "PE": ["Recife", "Caruaru"],
    "GO": ["Goiânia", "Anápolis"],
}
_CLIENT_PREFIXES = ["Farmácia", "Drogaria", "Distribuidora", "Comercial", "Centro Médico", "Hospital", "Rede", "Grupo"]
_CLIENT_MIDS     = ["Saúde", "Vida", "Brasil", "Nacional", "Popular", "Esperança", "Pharma", "Bio", "Med", "Plus", "Bem-Estar"]
_CLIENT_SUFIXES  = ["Ltda", "S/A", "Eireli", "ME"]
_STREET_NAMES    = ["Paulista", "Brasil", "das Nações", "do Comércio", "Industrial", "das Flores", "dos Pinheiros"]

CFOP_INTRA = "5102"
CFOP_INTER = "6102"

# ---------------------------------------------------------------------------
# Geradores de dados mestres
# ---------------------------------------------------------------------------


def _cnpj_fake(rng: random.Random) -> str:
    d = [str(rng.randint(0, 9)) for _ in range(14)]
    return f"{''.join(d[:2])}.{''.join(d[2:5])}.{''.join(d[5:8])}/{''.join(d[8:12])}-{''.join(d[12:14])}"


def _ie_fake(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def _ean13_fake(rng: random.Random) -> str:
    return "789" + "".join(str(rng.randint(0, 9)) for _ in range(10))


def gen_warehouses(ref_date: date, rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for w in WAREHOUSES:
        rows.append({
            **w,
            "Street":     f"Rua {rng.choice(_STREET_NAMES)} {rng.randint(100, 9999)}",
            "Country":    "BR",
            "IsDropShip": "N",
            "Inactive":   "N",
            "UpdateDate": ref_date,
            "UpdateTS":   90000,
        })
    return rows


def gen_items(ref_date: date, rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for (code, name, frgnname, grp, tax, reg, mng, prc, _) in _ITEMS_CATALOG:
        base_price = round(rng.uniform(15, 600), 2)
        rows.append({
            "ItemCode":    code,
            "ItemName":    name,
            "FrgnName":    frgnname,
            "ItmsGrpCod":  grp,
            "ItemType":    "I",
            "InvntItem":   "Y",
            "SellItem":    "Y" if prc == "M" else "N",
            "PrcrmntMtd":  prc,
            "SalUnitMsr":  "CX",
            "PurUnitMsr":  "CX",
            "InvntryUom":  "CX",
            "TaxCodeAR":   tax,
            "TaxCodeAP":   tax,
            "CodeBars":    _ean13_fake(rng) if prc == "M" else None,
            "RegNum":      reg,
            "ManBtchNum":  "Y",
            "MngMethod":   mng,
            "LastPurPrc":  base_price,
            "AvgPrice":    base_price,
            "validFor":    "Y",
            "frozenFor":   "N",
            "CreateDate":  ref_date,
            "CreateTS":    90000,
            "UpdateDate":  ref_date,
            "UpdateTS":    90000,
        })
    return rows


def gen_clients(n: int, ref_date: date, rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, n + 1):
        state  = rng.choice(_STATES)
        city   = rng.choice(_CITIES[state])
        name   = f"{rng.choice(_CLIENT_PREFIXES)} {rng.choice(_CLIENT_MIDS)} {rng.choice(_CLIENT_SUFIXES)}"
        d      = ref_date + timedelta(days=rng.randint(0, 20))
        ts     = rand_ts(rng)
        mid_slug = name.split()[1].lower()
        rows.append({
            "CardCode":  f"C{i:05d}",
            "CardName":  name,
            "CardType":  "C",
            "LicTradNum": _cnpj_fake(rng),
            "TaxIdNum":  _ie_fake(rng),
            "Address":   f"Av. {rng.choice(_STREET_NAMES)} {rng.randint(100, 9999)}",
            "ZipCode":   f"{rng.randint(10000, 99999):05d}-{rng.randint(100, 999):03d}",
            "City":      city,
            "State":     state,
            "Country":   "BR",
            "Phone1":    f"({rng.randint(11, 99)}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            "E_Mail":    f"compras@{mid_slug}{i:02d}.com.br",
            "GroupCode": rng.choice([1, 2, 3]),
            "SlpCode":   rng.randint(1, 5),
            "validFor":  "Y",
            "frozenFor": "N",
            "CreateDate": d,
            "CreateTS":  ts,
            "UpdateDate": d,
            "UpdateTS":  ts,
        })
    return rows


def gen_initial_stock(items: list[dict[str, Any]], ref_date: date) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        code = item["ItemCode"]
        if code in COLD_CHAIN_CODES:
            whs_list = ["PA02"]
        elif item["PrcrmntMtd"] == "B":
            whs_list = ["MP01"]
        else:
            whs_list = ["PA01"]
        for whs in whs_list:
            rows.append({
                "ItemCode":   code,
                "WhsCode":    whs,
                "OnHand":     round(rng_global.uniform(2000, 10000), 0),
                "IsCommited": 0.0,
                "OnOrder":    0.0,
                "MinLevel":   500.0,
                "MaxLevel":   20000.0,
                "UpdateDate": ref_date,
                "UpdateTS":   90000,
            })
    return rows


def gen_lots(items: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        code  = item["ItemCode"]
        shelf = ITEM_SHELF_MONTHS[code]
        if code in COLD_CHAIN_CODES:
            whs = "PA02"
        elif item["PrcrmntMtd"] == "B":
            whs = "MP01"
        else:
            whs = "PA01"

        mfg = START_DATE
        for seq in range(1, 8):
            adm = mfg + timedelta(days=rng.randint(1, 7))
            exp = mfg + timedelta(days=shelf * 30)
            qty = round(rng.uniform(2000, 15000), 0)
            # Lotes com vencimento antes de hoje já foram consumidos/vencidos
            status = "C" if exp < END_DATE - timedelta(days=30) else "A"
            batch_num = f"L{mfg.strftime('%Y%m')}{code[:4].upper()}{seq:03d}"
            ts = rand_ts(rng)
            rows.append({
                "ItemCode":   code,
                "BatchNum":   batch_num,
                "WhsCode":    whs,
                "MfgDate":    mfg,
                "ExpDate":    exp,
                "AdmDate":    adm,
                "Quantity":   qty,
                "Status":     status,
                "LotNumber":  f"FORN{rng.randint(100000, 999999)}",
                "SuppLotNum": batch_num,
                "Details":    None,
                "CreateDate": adm,
                "CreateTS":   ts,
                "UpdateDate": adm,
                "UpdateTS":   ts,
            })
            mfg = mfg + timedelta(days=rng.randint(60, 120))
            if mfg > END_DATE:
                break
    return rows


# ---------------------------------------------------------------------------
# Gerador de documentos (pedidos + NFs)
# ---------------------------------------------------------------------------


def _seasonal_weight(d: date) -> float:
    """Q1 e Q4 concentram mais vendas no setor farmacêutico."""
    if d.month in (1, 2, 3, 10, 11, 12):
        return 1.4
    if d.month in (6, 7, 8):
        return 0.75
    return 1.0


def _nfe_chave(inv_date: date, seq_nf: str, rng: random.Random) -> str:
    """Gera chave de acesso NF-e fictícia de exatamente 44 dígitos."""
    # cUF(2) AAMM(4) CNPJ(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) cDV(1) = 44
    return (
        "35"
        + inv_date.strftime("%y%m")
        + "".join(str(rng.randint(0, 9)) for _ in range(14))
        + "55"
        + "001"
        + seq_nf
        + "1"
        + "".join(str(rng.randint(0, 9)) for _ in range(8))
        + str(rng.randint(0, 9))
    )


@dataclass
class _DocCtx:
    order_num: int = 1
    inv_num:   int = 1
    clients:   list[dict[str, Any]] = field(default_factory=list)
    lots_by_item: dict[str, list[str]] = field(default_factory=dict)


def gen_orders_and_invoices(
    ctx: _DocCtx,
    rng: random.Random,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    orders: list[dict] = []
    order_lines: list[dict] = []
    invoices: list[dict] = []
    inv_lines: list[dict] = []

    current    = START_DATE + timedelta(days=31)  # mestres criados no primeiro mês
    last_month = None

    while current <= END_DATE:
        if current.weekday() >= 5:  # sem pedidos aos sábados e domingos
            current += timedelta(days=1)
            continue

        if current.month != last_month:
            log.info("  gerando pedidos de %s-%02d…", current.year, current.month)
            last_month = current.month

        n_orders = max(1, min(int(rng.gauss(3 * _seasonal_weight(current), 1.0)), 8))

        for _ in range(n_orders):
            client   = rng.choice(ctx.clients)
            n_lines  = rng.randint(1, 5)
            items    = rng.choices(SELLABLE_CODES, weights=ITEM_WEIGHTS, k=n_lines)
            items    = list(dict.fromkeys(items))  # deduplica mantendo ordem

            canceled = rng.random() < 0.04
            invoiced = not canceled and rng.random() < 0.90
            ts       = rand_ts(rng)
            due_date = current + timedelta(days=rng.randint(7, 30))
            cfop     = CFOP_INTRA if client["State"] == "SP" else CFOP_INTER

            doc_total = Decimal("0")
            vat_total = Decimal("0")
            line_buf: list[dict] = []

            for ln, item_code in enumerate(items):
                qty       = Decimal(str(round(rng.uniform(20, 500), 0)))
                price     = Decimal(str(round(rng.uniform(20, 800), 2)))
                disc_pct  = Decimal(str(rng.choice([0, 0, 0, 2, 5, 10])))
                price_net = price * (1 - disc_pct / 100)
                vat_rate  = Decimal("0.12")
                line_net  = qty * price_net
                line_vat  = line_net * vat_rate
                whs       = "PA02" if item_code in COLD_CHAIN_CODES else "PA01"
                lots      = ctx.lots_by_item.get(item_code, [])
                lot       = rng.choice(lots) if lots else None
                descr     = next(i[1] for i in _ITEMS_CATALOG if i[0] == item_code)

                doc_total += line_net
                vat_total += line_vat

                line_buf.append({
                    "LineNum":    ln,
                    "ItemCode":   item_code,
                    "Dscription": descr,
                    "Quantity":   float(qty),
                    "OpenQty":    0.0 if (invoiced or canceled) else float(qty),
                    "Price":      float(price),
                    "PriceAfVAT": float(price_net * (1 + vat_rate)),
                    "DiscPrcnt":  float(disc_pct),
                    "LineTotal":  float(line_net),
                    "VatSum":     float(line_vat),
                    "WhsCode":    whs,
                    "BatchNum":   lot,
                    "LineStatus": "C" if (invoiced or canceled) else "O",
                    "ShipDate":   due_date,
                    "TaxCode":    next((i[4] for i in _ITEMS_CATALOG if i[0] == item_code), None),
                    "CFOPCode":   cfop,
                })

            slp  = rng.randint(1, 5)
            grp  = rng.randint(1, 3)
            ref  = ctx.order_num  # DocNum local — resolve para DocEntry após INSERT

            orders.append({
                "DocNum":     ctx.order_num,
                "DocType":    "I",
                "DocStatus":  "C" if (invoiced or canceled) else "O",
                "CANCELED":   "Y" if canceled else "N",
                "CardCode":   client["CardCode"],
                "CardName":   client["CardName"],
                "DocDate":    current,
                "DocDueDate": due_date,
                "TaxDate":    current,
                "WhsCode":    "PA01",
                "DocTotal":   float(doc_total),
                "VatSum":     float(vat_total),
                "DiscSum":    0.0,
                "PaidToDate": float(doc_total) if invoiced else 0.0,
                "SlpCode":    slp,
                "GroupNum":   grp,
                "Comments":   None,
                "CreateDate": current,
                "CreateTS":   ts,
                "UpdateDate": current,
                "UpdateTS":   ts,
            })
            for lr in line_buf:
                order_lines.append({"_order_ref": ref, **lr})

            if invoiced:
                inv_date  = current + timedelta(days=rng.randint(0, 1))
                inv_due   = inv_date + timedelta(days=rng.randint(28, 60))
                inv_ts    = rand_ts(rng)
                seq_nf    = str(ctx.inv_num).zfill(9)
                invoices.append({
                    "DocNum":     ctx.inv_num,
                    "DocType":    "I",
                    "DocStatus":  "C",
                    "CANCELED":   "N",
                    "CardCode":   client["CardCode"],
                    "CardName":   client["CardName"],
                    "_base_ref":  ref,  # DocNum do ORDR de origem
                    "DocDate":    inv_date,
                    "DocDueDate": inv_due,
                    "TaxDate":    inv_date,
                    "FolioNum":   seq_nf,
                    "Series":     "001",
                    "ChaveNFe":   _nfe_chave(inv_date, seq_nf, rng),
                    "WhsCode":    "PA01",
                    "DocTotal":   float(doc_total),
                    "VatSum":     float(vat_total),
                    "DiscSum":    0.0,
                    "PaidToDate": float(doc_total),
                    "SlpCode":    slp,
                    "GroupNum":   grp,
                    "Comments":   None,
                    "CreateDate": inv_date,
                    "CreateTS":   inv_ts,
                    "UpdateDate": inv_date,
                    "UpdateTS":   inv_ts,
                })
                for ln_idx, lr in enumerate(line_buf):
                    inv_lines.append({
                        "_inv_ref":   ctx.inv_num,  # DocNum do OINV
                        "_base_ref":  ref,           # DocNum do ORDR de origem
                        "LineNum":    ln_idx,
                        "ItemCode":   lr["ItemCode"],
                        "Dscription": lr["Dscription"],
                        "Quantity":   lr["Quantity"],
                        "Price":      lr["Price"],
                        "PriceAfVAT": lr["PriceAfVAT"],
                        "DiscPrcnt":  lr["DiscPrcnt"],
                        "LineTotal":  lr["LineTotal"],
                        "VatSum":     lr["VatSum"],
                        "WhsCode":    lr["WhsCode"],
                        "BatchNum":   lr["BatchNum"],
                        "BaseLine":   lr["LineNum"],
                        "TaxCode":    lr["TaxCode"],
                        "CFOPCode":   lr["CFOPCode"],
                        "LineStatus": "C",
                    })
                ctx.inv_num += 1

            ctx.order_num += 1

        current += timedelta(days=1)

    return orders, order_lines, invoices, inv_lines


# ---------------------------------------------------------------------------
# Inserções em lote
# ---------------------------------------------------------------------------


def _batch_exec(cursor: pyodbc.Cursor, sql: str, rows: list[tuple]) -> None:
    for i in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[i : i + BATCH_SIZE])


def insert_warehouses(conn: pyodbc.Connection, rows: list[dict]) -> None:
    sql = """
        MERGE dbo.OWHS AS tgt
        USING (VALUES (?,?,?,?,?,?,?,?,?,?,?))
              AS src(WhsCode, WhsName, Street, City, State, Country,
                     Location, IsDropShip, Inactive, UpdateDate, UpdateTS)
        ON tgt.WhsCode = src.WhsCode
        WHEN NOT MATCHED THEN
            INSERT (WhsCode, WhsName, Street, City, State, Country,
                    Location, IsDropShip, Inactive, UpdateDate, UpdateTS)
            VALUES (src.WhsCode, src.WhsName, src.Street, src.City, src.State,
                    src.Country, src.Location, src.IsDropShip, src.Inactive,
                    src.UpdateDate, src.UpdateTS)
        WHEN MATCHED THEN
            UPDATE SET WhsName    = src.WhsName,
                       Street     = src.Street,
                       City       = src.City,
                       State      = src.State,
                       UpdateDate = src.UpdateDate,
                       UpdateTS   = src.UpdateTS;
    """
    tuples = [
        (r["WhsCode"], r["WhsName"], r["Street"], r["City"], r["State"], r["Country"],
         r["Location"], r["IsDropShip"], r["Inactive"], r["UpdateDate"], r["UpdateTS"])
        for r in rows
    ]
    with conn.cursor() as cur:
        _batch_exec(cur, sql, tuples)
    conn.commit()
    log.info("OWHS: %d linhas", len(rows))


def insert_items(conn: pyodbc.Connection, rows: list[dict]) -> None:
    sql = """
        MERGE dbo.OITM AS tgt
        USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?))
              AS src(ItemCode, ItemName, FrgnName, ItmsGrpCod, ItemType, InvntItem,
                     SellItem, PrcrmntMtd, SalUnitMsr, PurUnitMsr, InvntryUom,
                     TaxCodeAR, TaxCodeAP, CodeBars, RegNum, ManBtchNum, MngMethod,
                     LastPurPrc, AvgPrice, validFor, frozenFor,
                     CreateDate, CreateTS, UpdateDate, UpdateTS)
        ON tgt.ItemCode = src.ItemCode
        WHEN NOT MATCHED THEN
            INSERT (ItemCode, ItemName, FrgnName, ItmsGrpCod, ItemType, InvntItem,
                    SellItem, PrcrmntMtd, SalUnitMsr, PurUnitMsr, InvntryUom,
                    TaxCodeAR, TaxCodeAP, CodeBars, RegNum, ManBtchNum, MngMethod,
                    LastPurPrc, AvgPrice, validFor, frozenFor,
                    CreateDate, CreateTS, UpdateDate, UpdateTS)
            VALUES (src.ItemCode, src.ItemName, src.FrgnName, src.ItmsGrpCod, src.ItemType,
                    src.InvntItem, src.SellItem, src.PrcrmntMtd, src.SalUnitMsr,
                    src.PurUnitMsr, src.InvntryUom, src.TaxCodeAR, src.TaxCodeAP,
                    src.CodeBars, src.RegNum, src.ManBtchNum, src.MngMethod,
                    src.LastPurPrc, src.AvgPrice, src.validFor, src.frozenFor,
                    src.CreateDate, src.CreateTS, src.UpdateDate, src.UpdateTS)
        WHEN MATCHED THEN
            UPDATE SET ItemName   = src.ItemName,
                       TaxCodeAR  = src.TaxCodeAR,
                       TaxCodeAP  = src.TaxCodeAP,
                       LastPurPrc = src.LastPurPrc,
                       AvgPrice   = src.AvgPrice,
                       validFor   = src.validFor,
                       frozenFor  = src.frozenFor,
                       UpdateDate = src.UpdateDate,
                       UpdateTS   = src.UpdateTS;
    """
    tuples = [
        (r["ItemCode"], r["ItemName"], r["FrgnName"], r["ItmsGrpCod"], r["ItemType"],
         r["InvntItem"], r["SellItem"], r["PrcrmntMtd"], r["SalUnitMsr"],
         r["PurUnitMsr"], r["InvntryUom"], r["TaxCodeAR"], r["TaxCodeAP"],
         r["CodeBars"], r["RegNum"], r["ManBtchNum"], r["MngMethod"],
         r["LastPurPrc"], r["AvgPrice"], r["validFor"], r["frozenFor"],
         r["CreateDate"], r["CreateTS"], r["UpdateDate"], r["UpdateTS"])
        for r in rows
    ]
    with conn.cursor() as cur:
        _batch_exec(cur, sql, tuples)
    conn.commit()
    log.info("OITM: %d linhas", len(rows))


def insert_clients(conn: pyodbc.Connection, rows: list[dict]) -> None:
    sql = """
        MERGE dbo.OCRD AS tgt
        USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?))
              AS src(CardCode, CardName, CardType, LicTradNum, TaxIdNum,
                     Address, ZipCode, City, State, Country, Phone1, E_Mail,
                     GroupCode, SlpCode, validFor, frozenFor,
                     CreateDate, CreateTS, UpdateDate, UpdateTS)
        ON tgt.CardCode = src.CardCode
        WHEN NOT MATCHED THEN
            INSERT (CardCode, CardName, CardType, LicTradNum, TaxIdNum,
                    Address, ZipCode, City, State, Country, Phone1, E_Mail,
                    GroupCode, SlpCode, validFor, frozenFor,
                    CreateDate, CreateTS, UpdateDate, UpdateTS)
            VALUES (src.CardCode, src.CardName, src.CardType, src.LicTradNum, src.TaxIdNum,
                    src.Address, src.ZipCode, src.City, src.State, src.Country,
                    src.Phone1, src.E_Mail, src.GroupCode, src.SlpCode,
                    src.validFor, src.frozenFor,
                    src.CreateDate, src.CreateTS, src.UpdateDate, src.UpdateTS)
        WHEN MATCHED THEN
            UPDATE SET CardName   = src.CardName,
                       Address    = src.Address,
                       City       = src.City,
                       State      = src.State,
                       Phone1     = src.Phone1,
                       E_Mail     = src.E_Mail,
                       validFor   = src.validFor,
                       frozenFor  = src.frozenFor,
                       UpdateDate = src.UpdateDate,
                       UpdateTS   = src.UpdateTS;
    """
    tuples = [
        (r["CardCode"], r["CardName"], r["CardType"], r["LicTradNum"], r["TaxIdNum"],
         r["Address"], r["ZipCode"], r["City"], r["State"], r["Country"],
         r["Phone1"], r["E_Mail"], r["GroupCode"], r["SlpCode"],
         r["validFor"], r["frozenFor"], r["CreateDate"], r["CreateTS"],
         r["UpdateDate"], r["UpdateTS"])
        for r in rows
    ]
    with conn.cursor() as cur:
        _batch_exec(cur, sql, tuples)
    conn.commit()
    log.info("OCRD: %d linhas", len(rows))


def insert_stock(conn: pyodbc.Connection, rows: list[dict]) -> None:
    sql = """
        MERGE dbo.OITW AS tgt
        USING (VALUES (?,?,?,?,?,?,?,?,?))
              AS src(ItemCode, WhsCode, OnHand, IsCommited, OnOrder,
                     MinLevel, MaxLevel, UpdateDate, UpdateTS)
        ON tgt.ItemCode = src.ItemCode AND tgt.WhsCode = src.WhsCode
        WHEN NOT MATCHED THEN
            INSERT (ItemCode, WhsCode, OnHand, IsCommited, OnOrder,
                    MinLevel, MaxLevel, UpdateDate, UpdateTS)
            VALUES (src.ItemCode, src.WhsCode, src.OnHand, src.IsCommited, src.OnOrder,
                    src.MinLevel, src.MaxLevel, src.UpdateDate, src.UpdateTS)
        WHEN MATCHED THEN
            UPDATE SET OnHand     = src.OnHand,
                       IsCommited = src.IsCommited,
                       OnOrder    = src.OnOrder,
                       MinLevel   = src.MinLevel,
                       MaxLevel   = src.MaxLevel,
                       UpdateDate = src.UpdateDate,
                       UpdateTS   = src.UpdateTS;
    """
    tuples = [
        (r["ItemCode"], r["WhsCode"], r["OnHand"], r["IsCommited"], r["OnOrder"],
         r["MinLevel"], r["MaxLevel"], r["UpdateDate"], r["UpdateTS"])
        for r in rows
    ]
    with conn.cursor() as cur:
        _batch_exec(cur, sql, tuples)
    conn.commit()
    log.info("OITW: %d linhas", len(rows))


def insert_lots(conn: pyodbc.Connection, rows: list[dict]) -> None:
    sql = """
        MERGE dbo.OBTN AS tgt
        USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?))
              AS src(ItemCode, BatchNum, WhsCode, MfgDate, ExpDate, AdmDate,
                     Quantity, Status, LotNumber, SuppLotNum, Details,
                     CreateDate, CreateTS, UpdateDate, UpdateTS)
        ON tgt.ItemCode = src.ItemCode
           AND tgt.BatchNum = src.BatchNum
           AND tgt.WhsCode  = src.WhsCode
        WHEN NOT MATCHED THEN
            INSERT (ItemCode, BatchNum, WhsCode, MfgDate, ExpDate, AdmDate,
                    Quantity, Status, LotNumber, SuppLotNum, Details,
                    CreateDate, CreateTS, UpdateDate, UpdateTS)
            VALUES (src.ItemCode, src.BatchNum, src.WhsCode, src.MfgDate, src.ExpDate,
                    src.AdmDate, src.Quantity, src.Status, src.LotNumber, src.SuppLotNum,
                    src.Details, src.CreateDate, src.CreateTS, src.UpdateDate, src.UpdateTS)
        WHEN MATCHED THEN
            UPDATE SET Quantity   = src.Quantity,
                       Status     = src.Status,
                       UpdateDate = src.UpdateDate,
                       UpdateTS   = src.UpdateTS;
    """
    tuples = [
        (r["ItemCode"], r["BatchNum"], r["WhsCode"], r["MfgDate"], r["ExpDate"],
         r["AdmDate"], r["Quantity"], r["Status"], r["LotNumber"], r["SuppLotNum"],
         r["Details"], r["CreateDate"], r["CreateTS"], r["UpdateDate"], r["UpdateTS"])
        for r in rows
    ]
    with conn.cursor() as cur:
        _batch_exec(cur, sql, tuples)
    conn.commit()
    log.info("OBTN: %d linhas", len(rows))


def insert_orders(
    conn: pyodbc.Connection,
    orders: list[dict],
    order_lines: list[dict],
) -> dict[int, int]:
    """Insere ORDR e RDR1. Retorna mapa {DocNum → real DocEntry IDENTITY}.
    Se ORDR já contiver dados, lê o mapa existente sem re-inserir
    (use --reset para recarregar do zero)."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(1) FROM dbo.ORDR")
        if cur.fetchone()[0] > 0:
            log.warning("ORDR já populado — lendo mapa DocNum→DocEntry sem re-inserir; use --reset para recarga completa.")
            cur.execute("SELECT DocNum, DocEntry FROM dbo.ORDR")
            return {row[0]: row[1] for row in cur.fetchall()}

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
    doc_num_to_entry: dict[int, int] = {}

    with conn.cursor() as cur:
        for r in orders:
            cur.execute(sql_hdr, (
                r["DocNum"], r["DocType"], r["DocStatus"], r["CANCELED"],
                r["CardCode"], r["CardName"],
                r["DocDate"], r["DocDueDate"], r["TaxDate"], r["WhsCode"],
                r["DocTotal"], r["VatSum"], r["DiscSum"], r["PaidToDate"],
                r["SlpCode"], r["GroupNum"], r["Comments"],
                r["CreateDate"], r["CreateTS"], r["UpdateDate"], r["UpdateTS"],
            ))
            row = cur.fetchone()
            doc_num_to_entry[row[1]] = row[0]  # DocNum → DocEntry

        line_tuples = []
        for lr in order_lines:
            entry = doc_num_to_entry.get(lr["_order_ref"])
            if entry is None:
                continue
            line_tuples.append((
                entry, lr["LineNum"], lr["ItemCode"], lr["Dscription"],
                lr["Quantity"], lr["OpenQty"],
                lr["Price"], lr["PriceAfVAT"], lr["DiscPrcnt"],
                lr["LineTotal"], lr["VatSum"],
                lr["WhsCode"], lr["BatchNum"], lr["LineStatus"], lr["ShipDate"],
            ))
        _batch_exec(cur, sql_line, line_tuples)

    conn.commit()
    log.info("ORDR: %d / RDR1: %d linhas", len(orders), len(order_lines))
    return doc_num_to_entry


def insert_invoices(
    conn: pyodbc.Connection,
    invoices: list[dict],
    inv_lines: list[dict],
    order_num_to_entry: dict[int, int],
) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(1) FROM dbo.OINV")
        if cur.fetchone()[0] > 0:
            log.warning("OINV já populado — pulando inserção; use --reset para recarga completa.")
            return

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
    sql_line = """
        INSERT INTO dbo.INV1
            (DocEntry, LineNum, ItemCode, Dscription, Quantity,
             Price, PriceAfVAT, DiscPrcnt, LineTotal, VatSum,
             WhsCode, BatchNum, BaseEntry, BaseLine,
             TaxCode, CFOPCode, LineStatus)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    inv_num_to_entry: dict[int, int] = {}

    with conn.cursor() as cur:
        for r in invoices:
            real_base = order_num_to_entry.get(r["_base_ref"])
            cur.execute(sql_hdr, (
                r["DocNum"], r["DocType"], r["DocStatus"], r["CANCELED"],
                r["CardCode"], r["CardName"],
                real_base,
                r["DocDate"], r["DocDueDate"], r["TaxDate"],
                r["FolioNum"], r["Series"], r["ChaveNFe"], r["WhsCode"],
                r["DocTotal"], r["VatSum"], r["DiscSum"], r["PaidToDate"],
                r["SlpCode"], r["GroupNum"], r["Comments"],
                r["CreateDate"], r["CreateTS"], r["UpdateDate"], r["UpdateTS"],
            ))
            row = cur.fetchone()
            inv_num_to_entry[row[1]] = row[0]

        line_tuples = []
        for lr in inv_lines:
            entry     = inv_num_to_entry.get(lr["_inv_ref"])
            real_base = order_num_to_entry.get(lr["_base_ref"])
            if entry is None:
                continue
            line_tuples.append((
                entry, lr["LineNum"], lr["ItemCode"], lr["Dscription"],
                lr["Quantity"],
                lr["Price"], lr["PriceAfVAT"], lr["DiscPrcnt"],
                lr["LineTotal"], lr["VatSum"],
                lr["WhsCode"], lr["BatchNum"], real_base, lr["BaseLine"],
                lr["TaxCode"], lr["CFOPCode"], lr["LineStatus"],
            ))
        _batch_exec(cur, sql_line, line_tuples)

    conn.commit()
    log.info("OINV: %d / INV1: %d linhas", len(invoices), len(inv_lines))


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def reset_tables(conn: pyodbc.Connection) -> None:
    # Ordem respeita FKs: filhos antes dos pais
    tables_ordered = ["INV1", "OINV", "RDR1", "ORDR", "OBTN", "OITW", "OCRD", "OITM", "OWHS"]
    identity_tables = {"OBTN", "ORDR", "OINV"}
    with conn.cursor() as cur:
        for t in tables_ordered:
            cur.execute(f"DELETE FROM dbo.{t}")
    conn.commit()  # commit antes do DBCC; DBCC falha dentro de transação aberta no Azure SQL
    with conn.cursor() as cur:
        for t in identity_tables:
            cur.execute(f"DBCC CHECKIDENT ('dbo.{t}', RESEED, 0)")
    conn.commit()
    log.info("Tabelas resetadas: %s", tables_ordered)


# ---------------------------------------------------------------------------
# Estado global do RNG (reiniciado em main para reprodutibilidade)
# ---------------------------------------------------------------------------

rng_global: random.Random = random.Random(SEED)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga histórica SBO_PHARMA_LAB")
    parser.add_argument("--reset",   action="store_true", help="Limpa as tabelas antes da carga")
    parser.add_argument("--dry-run", action="store_true", help="Gera dados mas não conecta ao banco")
    args = parser.parse_args()

    global rng_global
    rng_global = random.Random(SEED)

    log.info("Período: %s → %s", START_DATE, END_DATE)

    ref = START_DATE
    t0  = time.monotonic()

    log.info("Gerando mestres…")
    whs_rows    = gen_warehouses(ref, rng_global)
    item_rows   = gen_items(ref, rng_global)
    client_rows = gen_clients(50, ref, rng_global)
    stock_rows  = gen_initial_stock(item_rows, ref)
    lot_rows    = gen_lots(item_rows, rng_global)

    lots_by_item: dict[str, list[str]] = {}
    for lot in lot_rows:
        lots_by_item.setdefault(lot["ItemCode"], []).append(lot["BatchNum"])

    log.info("Gerando pedidos e notas fiscais…")
    ctx = _DocCtx(order_num=1, inv_num=1, clients=client_rows, lots_by_item=lots_by_item)
    orders, order_lines, invoices, inv_lines = gen_orders_and_invoices(ctx, rng_global)

    log.info(
        "Volumes gerados — OCRD:%d OITM:%d OWHS:%d OITW:%d OBTN:%d "
        "ORDR:%d RDR1:%d OINV:%d INV1:%d (%.1fs)",
        len(client_rows), len(item_rows), len(whs_rows), len(stock_rows), len(lot_rows),
        len(orders), len(order_lines), len(invoices), len(inv_lines),
        time.monotonic() - t0,
    )

    if args.dry_run:
        log.info("--dry-run: nenhuma conexão aberta.")
        return

    log.info("Conectando ao banco…")
    conn = get_connection()
    try:
        if args.reset:
            reset_tables(conn)

        insert_warehouses(conn, whs_rows)
        insert_items(conn, item_rows)
        insert_clients(conn, client_rows)
        insert_stock(conn, stock_rows)
        insert_lots(conn, lot_rows)
        order_map = insert_orders(conn, orders, order_lines)
        insert_invoices(conn, invoices, inv_lines, order_map)

        log.info("Carga concluída em %.1fs.", time.monotonic() - t0)
    finally:
        conn.close()
        log.info("Conexão fechada.")


if __name__ == "__main__":
    main()
