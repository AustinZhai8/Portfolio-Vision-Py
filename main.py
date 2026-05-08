import json
import sys
from collections import defaultdict

# Force UTF-8 output so bar chart characters render correctly on Windows
sys.stdout.reconfigure(encoding="utf-8")

# ── Load data ────────────────────────────────────────────────────────────────

with open("data/etf_data.json", "r") as f:
    DATA = json.load(f)

ETF_DATA = DATA["etfs"]
STOCK_DATA = DATA["stocks"]

# Update this rate as needed
USDCAD = 1.3850

TICKER_ALIASES = {
    "VFV": "VFV.TO",
    "QQC": "QQC.F",
    "XIU": "XIU.TO",
    "XIC": "XIC.TO",
    "VDY": "VDY.TO",
    "QQQM": "QQQ",
    "ZCN": "ZCN.TO",
    "HXS": "HXS.TO",
    "VEQT": "VEQT.TO",
    "XEQT": "VEQT.TO",
    "VGRO": "VGRO.TO",
    "ZLB": "ZLB.TO",
    "XEI": "XEI.TO",
    "CNDX": "CNDX.TO",
    "DMEU": "DMEU.TO",
    "CUEI": "CUEI.TO",
    "QAH": "QAH.TO",
    "DMEC": "DMEC.TO",
    "HEB": "HEB.TO",
    "XBAL": "XBAL.TO",
    "FEQT": "FEQT.TO",
    "FGRO": "FGRO.TO",
    "FBAL": "FBAL.TO",
    "XDIV": "XDIV.TO",
    "XGD": "XGD.TO",
    "ZLU": "ZLU.TO",
    "ZUQ": "ZUQ.TO",
    "XRE": "XRE.TO",
    "EQL": "EQL.TO",
    "EQL.F": "EQL.F.TO",
    "ITOT": "VTI",
    "ZEQT": "ZEQT.TO",
    "FCCM": "FCCM.TO",
    "FINN": "FINN.TO",
}


def resolve_ticker(ticker):
    t = ticker.upper()
    if t in TICKER_ALIASES:
        return TICKER_ALIASES[t]
    # Auto-try .TO suffix so users can type RY instead of RY.TO
    if t not in ETF_DATA and t not in STOCK_DATA:
        candidate = t + ".TO"
        if candidate in ETF_DATA or candidate in STOCK_DATA:
            return candidate
    return t


def display_ticker(ticker):
    """Strip .TO suffix for cleaner display."""
    return ticker[:-3] if ticker.endswith(".TO") else ticker


def infer_currency(ticker):
    """Guess currency from ticker: .TO / .F suffix → CAD, else → USD."""
    t = resolve_ticker(ticker.upper())
    if t.endswith(".TO") or t.endswith(".F"):
        return "CAD"
    return "USD"


def convert_amount(amount, from_ccy, to_ccy):
    if from_ccy == to_ccy:
        return amount
    if from_ccy == "USD" and to_ccy == "CAD":
        return amount * USDCAD
    return amount / USDCAD


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_etf_holdings(etf_ticker):
    etf = ETF_DATA.get(resolve_ticker(etf_ticker))
    if not etf:
        return None
    if "holdings_same_as" in etf:
        return get_etf_holdings(etf["holdings_same_as"])
    return etf["holdings"]


def is_etf(ticker):
    return resolve_ticker(ticker) in ETF_DATA


def decompose_portfolio(portfolio, _depth=0):
    """
    portfolio: dict of {ticker: dollar_amount}
    Returns a flat dict of {stock_ticker: dollar_exposure}.
    Recursively decomposes ETF-of-ETFs up to depth 5.
    """
    if _depth > 5:
        return {}, []

    result = defaultdict(float)
    unknown = []

    for ticker, amount in portfolio.items():
        ticker = resolve_ticker(ticker)

        if is_etf(ticker):
            holdings = get_etf_holdings(ticker)
            if not holdings:
                unknown.append(ticker)
                continue

            for holding in holdings:
                fraction = holding["weight"] / 100.0
                sub_ticker = resolve_ticker(holding["ticker"].upper())
                sub_amount = amount * fraction

                if is_etf(sub_ticker):
                    sub_result, sub_unknown = decompose_portfolio(
                        {sub_ticker: sub_amount}, _depth + 1
                    )
                    for k, v in sub_result.items():
                        result[k] += v
                    unknown.extend(sub_unknown)
                else:
                    result[sub_ticker] += sub_amount
        else:
            result[ticker] += amount

    return dict(result), unknown


def get_stock_info(ticker):
    info = STOCK_DATA.get(resolve_ticker(ticker), {})
    return {
        "name": info.get("name", ticker),
        "sector": info.get("sector", "Unknown"),
        "country": info.get("country", "Unknown"),
    }


def breakdown_by_sector(decomposed):
    sectors = defaultdict(float)
    for ticker, amount in decomposed.items():
        sectors[get_stock_info(ticker)["sector"]] += amount
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def breakdown_by_country(decomposed):
    countries = defaultdict(float)
    for ticker, amount in decomposed.items():
        countries[get_stock_info(ticker)["country"]] += amount
    return dict(sorted(countries.items(), key=lambda x: x[1], reverse=True))


def print_report(entries, portfolio, decomposed, sectors, countries, unknown, display_currency):
    """
    entries:   {ticker: (original_amount, original_currency)}
    portfolio: {ticker: amount_in_display_currency}
    """
    ccy_label = "CAD" if display_currency == "CAD" else "USD"
    portfolio_total = sum(portfolio.values())
    total = sum(decomposed.values())

    print("\n" + "=" * 62)
    print(f"  PORTFOLIO DECOMPOSITION  |  amounts in {ccy_label}")
    print("=" * 62)

    print("\n  Input Portfolio")
    print(f"  {'Ticker':<12} {'Type':<7} {'Amount':>14}  {'Original':>16}")
    print(f"  {'-'*12} {'-'*7} {'-'*14}  {'-'*16}")
    for ticker, (orig_amount, orig_ccy) in entries.items():
        label = "ETF" if is_etf(ticker) else "Stock"
        converted = portfolio[ticker]
        dticker = display_ticker(ticker)
        if orig_ccy != display_currency:
            orig_note = f"{orig_amount:,.2f} {orig_ccy}"
        else:
            orig_note = ""
        print(f"  {dticker:<12} {label:<7} {converted:>14,.2f}  {orig_note:>16}")

    if display_currency == "CAD":
        print(f"  (1 USD = {USDCAD} CAD)")
    else:
        print(f"  (1 CAD = {1/USDCAD:.4f} USD)")

    if unknown:
        print(f"\n  WARNING — unrecognized tickers skipped: {', '.join(display_ticker(t) for t in unknown)}")

    print(f"\n  Top Holdings")
    print(f"  {'Ticker':<10} {'Name':<40} {'Amount':>14}  {'%':>6}")
    print(f"  {'-'*10} {'-'*40} {'-'*14}  {'-'*6}")
    sorted_holdings = sorted(decomposed.items(), key=lambda x: x[1], reverse=True)
    for ticker, amount in sorted_holdings[:20]:
        info = get_stock_info(ticker)
        pct = (amount / portfolio_total) * 100
        print(f"  {display_ticker(ticker):<10} {info['name']:<40} {amount:>14,.2f}  {pct:>5.1f}%")
    if len(sorted_holdings) > 20:
        remaining = sum(v for _, v in sorted_holdings[20:])
        print(f"  {'...':<10} {'(remaining holdings)':<40} {remaining:>14,.2f}  {(remaining/portfolio_total)*100:>5.1f}%")

    BAR_WIDTH = 36
    print(f"\n  Sector Breakdown")
    for sector, amount in sectors.items():
        pct = (amount / portfolio_total) * 100
        bar = "█" * int(pct / 100 * BAR_WIDTH)
        print(f"  {sector:<26} {bar:<{BAR_WIDTH}}  {pct:>5.1f}%")

    print(f"\n  Geographic Breakdown")
    for country, amount in countries.items():
        pct = (amount / portfolio_total) * 100
        bar = "█" * int(pct / 100 * BAR_WIDTH)
        print(f"  {country:<26} {bar:<{BAR_WIDTH}}  {pct:>5.1f}%")

    coverage = (total / portfolio_total * 100) if portfolio_total else 0
    print(f"\n  Total:      {portfolio_total:>14,.2f} {ccy_label}")
    print(f"  Captured:   {total:>14,.2f} {ccy_label}  ({coverage:.1f}%)")
    if coverage < 99:
        print(f"  Untracked:  {portfolio_total - total:>14,.2f} {ccy_label}  ({100 - coverage:.1f}% — below data cutoff)")
    print("=" * 62 + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def get_portfolio_from_user():
    """
    Returns {ticker: (amount, currency)}.
    Input format: TICKER AMOUNT [USD|CAD]
    Currency is inferred from the ticker suffix if omitted.
    """
    print("\nEnter your portfolio.")
    print("Format: TICKER AMOUNT [USD|CAD]")
    print("  e.g.  VFV 5000 CAD   or   AAPL 1000 USD   or   VOO 3000")
    print("  (currency inferred from ticker if omitted — .TO tickers = CAD)")
    print("Type 'done' when finished.\n")

    entries = {}
    while True:
        entry = input("  > ").strip()
        if entry.lower() == "done":
            break
        parts = entry.split()
        if len(parts) not in (2, 3):
            print("  Invalid format. Use: TICKER AMOUNT [USD|CAD]")
            continue
        ticker = parts[0].upper()
        try:
            amount = float(parts[1])
        except ValueError:
            print("  Amount must be a number.")
            continue
        if len(parts) == 3:
            currency = parts[2].upper()
            if currency not in ("USD", "CAD"):
                print("  Currency must be USD or CAD.")
                continue
        else:
            currency = infer_currency(ticker)
        entries[ticker] = (amount, currency)
    return entries


if __name__ == "__main__":
    entries = get_portfolio_from_user()

    if not entries:
        print("No portfolio entered. Exiting.")
    else:
        currencies_used = {ccy for _, ccy in entries.values()}

        if len(currencies_used) == 1:
            display_currency = currencies_used.pop()
        else:
            print(f"\nMixed currencies detected (USD and CAD).")
            choice = ""
            while choice not in ("USD", "CAD"):
                choice = input("Display results in USD or CAD? ").strip().upper()
            display_currency = choice

        portfolio = {
            ticker: convert_amount(amount, ccy, display_currency)
            for ticker, (amount, ccy) in entries.items()
        }

        decomposed, unknown = decompose_portfolio(portfolio)
        sectors = breakdown_by_sector(decomposed)
        countries = breakdown_by_country(decomposed)
        print_report(entries, portfolio, decomposed, sectors, countries, unknown, display_currency)
