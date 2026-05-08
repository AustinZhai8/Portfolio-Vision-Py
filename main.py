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

# Only keep cross-ticker mappings where the input name differs from the actual ticker
TICKER_ALIASES = {
    "QQQM": "QQQ",       # User shortcut to US QQQ
    "ITOT": "VTI",       # User shortcut to US VTI
    "XEQT": "VEQT.TO",   # Alternative name for VEQT
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
    # Strip .TO suffix for cleaner display
    if ticker.endswith(".TO"):
        # Get all characters except the last 3
        return ticker[:-3]
    else:
        return ticker


def infer_currency(ticker):
    # Guess currency from ticker: .TO / .F suffix → CAD, else → USD
    t = resolve_ticker(ticker.upper())
    if t.endswith(".TO") or t.endswith(".F"):
        return "CAD"
    return "USD"


def convert_amount(amount, from_ccy, to_ccy):
    if from_ccy == to_ccy:
        return amount
    if from_ccy == "USD" and to_ccy == "CAD":
        return amount * USDCAD
    else:
        # Convert from CAD to USD
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
    # portfolio: dict of {ticker: dollar_amount} Returns a flat dict of {stock_ticker: dollar_exposure}. Recursively decomposes ETF-of-ETFs up to depth 5.
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
                        result[k] = result[k] + v
                    for item in sub_unknown:
                        unknown.append(item)
                else:
                    result[sub_ticker] = result[sub_ticker] + sub_amount
        else:
            result[ticker] = result[ticker] + amount

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
        info = get_stock_info(ticker)
        sector = info["sector"]
        sectors[sector] = sectors[sector] + amount
    
    # Sort by amount (highest first) - manual sorting
    sector_list = list(sectors.items())
    
    # Repeatedly find the item with highest amount and move it to sorted position
    sorted_list = []
    while sector_list:
        highest_sector = None
        highest_amount = -1
        highest_index = -1
        
        for i in range(len(sector_list)):
            sector, amount = sector_list[i]
            if amount > highest_amount:
                highest_amount = amount
                highest_sector = sector
                highest_index = i
        
        sorted_list.append((highest_sector, highest_amount))
        sector_list.pop(highest_index)
    
    result = {}
    for sector, amount in sorted_list:
        result[sector] = amount
    return result


def breakdown_by_country(decomposed):
    countries = defaultdict(float)
    for ticker, amount in decomposed.items():
        info = get_stock_info(ticker)
        country = info["country"]
        countries[country] = countries[country] + amount
    
    # Sort by amount (highest first) - manual sorting
    country_list = list(countries.items())
    
    # Repeatedly find the item with highest amount and move it to sorted position
    sorted_list = []
    while country_list:
        highest_country = None
        highest_amount = -1
        highest_index = -1
        
        for i in range(len(country_list)):
            country, amount = country_list[i]
            if amount > highest_amount:
                highest_amount = amount
                highest_country = country
                highest_index = i
        
        sorted_list.append((highest_country, highest_amount))
        country_list.pop(highest_index)
    
    result = {}
    for country, amount in sorted_list:
        result[country] = amount
    return result


def print_report(entries, portfolio, decomposed, sectors, countries, unknown, display_currency):
    # entries:   {ticker: (original_amount, original_currency)}
    # portfolio: {ticker: amount_in_display_currency}
    ccy_label = "CAD" if display_currency == "CAD" else "USD"
    portfolio_total = sum(portfolio.values())
    total = sum(decomposed.values())

    print("\n" + "=" * 62)
    print(f"  PORTFOLIO DECOMPOSITION  |  amounts in {ccy_label}")
    print("=" * 62)

    print("\n  Input Portfolio")
    print("  " + "-" * 80)
    
    for ticker in entries:
        orig_amount, orig_ccy = entries[ticker]
        label = "ETF" if is_etf(ticker) else "Stock"
        converted = portfolio[ticker]
        dticker = display_ticker(ticker)
        
        if orig_ccy != display_currency:
            orig_note = f"{orig_amount:,.2f} {orig_ccy}"
        else:
            orig_note = ""
        
        print(f"  {dticker}  {label}  ${converted:,.2f}  {orig_note}")

    if display_currency == "CAD":
        print(f"  (1 USD = {USDCAD} CAD)")
    else:
        rate_usd_per_cad = 1 / USDCAD
        print(f"  (1 CAD = {rate_usd_per_cad:.4f} USD)")

    if unknown:
        # Build list of unknown tickers to display
        unknown_list = []
        for t in unknown:
            unknown_list.append(display_ticker(t))
        unknown_str = ", ".join(unknown_list)
        print(f"\n  WARNING — unrecognized tickers skipped: {unknown_str}")

    print("\n  Top Holdings")
    print("  Ticker     Name                                        Amount           %")
    print("  " + "-" * 75)
    
    # Sort holdings by amount (highest first)
    holding_list = list(decomposed.items())
    sorted_holdings = []
    while holding_list:
        highest_ticker = None
        highest_amount = -1
        highest_index = -1
        
        for i in range(len(holding_list)):
            ticker, amount = holding_list[i]
            if amount > highest_amount:
                highest_amount = amount
                highest_ticker = ticker
                highest_index = i
        
        sorted_holdings.append((highest_ticker, highest_amount))
        holding_list.pop(highest_index)
    
    # Show top 20 holdings
    for i in range(20):
        if i >= len(sorted_holdings):
            break
        
        ticker, amount = sorted_holdings[i]
        info = get_stock_info(ticker)
        pct = (amount / portfolio_total) * 100
        display_name = display_ticker(ticker)
        stock_name = info['name']
        
        # Truncate name if too long
        if len(stock_name) > 43:
            stock_name = stock_name[:40] + "..."
        
        print(f"  {display_name:<10} {stock_name:<43} ${amount:>12,.2f}  {pct:>5.1f}%")
    
    if len(sorted_holdings) > 20:
        remaining = 0
        for i in range(20, len(sorted_holdings)):
            _, amount = sorted_holdings[i]
            remaining = remaining + amount
        
        remaining_pct = (remaining / portfolio_total) * 100
        print(f"  {'...':<10} {'(remaining holdings)':<43} ${remaining:>12,.2f}  {remaining_pct:>5.1f}%")

    BAR_WIDTH = 30
    print("\n  Sector Breakdown")
    for sector, amount in sectors.items():
        pct = (amount / portfolio_total) * 100
        bar_length = int(pct / 100 * BAR_WIDTH)
        bar = "█" * bar_length
        bar_padded = bar.ljust(BAR_WIDTH)
        print(f"  {sector:<26} {bar_padded}  {pct:>5.1f}%")

    print("\n  Geographic Breakdown")
    for country, amount in countries.items():
        pct = (amount / portfolio_total) * 100
        bar_length = int(pct / 100 * BAR_WIDTH)
        bar = "█" * bar_length
        bar_padded = bar.ljust(BAR_WIDTH)
        print(f"  {country:<26} {bar_padded}  {pct:>5.1f}%")

    coverage = (total / portfolio_total * 100) if portfolio_total else 0
    print(f"\n  Total:      ${portfolio_total:,.2f} {ccy_label}")
    print(f"  Captured:   ${total:,.2f} {ccy_label}  ({coverage:.1f}%)")
    
    if coverage < 99:
        uncovered = portfolio_total - total
        uncovered_pct = 100 - coverage
        print(f"  Untracked:  ${uncovered:,.2f} {ccy_label}  ({uncovered_pct:.1f}% — below data cutoff)")
    
    print("=" * 62 + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def get_portfolio_from_user():
    # Returns {ticker: (amount, currency)}
    # Input format: TICKER AMOUNT [USD|CAD]
    # Currency is inferred from the ticker suffix if omitted
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
        # Collect all currencies used
        currencies_used = set()
        for ticker in entries:
            amount, ccy = entries[ticker]
            currencies_used.add(ccy)

        if len(currencies_used) == 1:
            display_currency = currencies_used.pop()
        else:
            print(f"\nMixed currencies detected (USD and CAD).")
            choice = ""
            while choice not in ("USD", "CAD"):
                choice = input("Display results in USD or CAD? ").strip().upper()
            display_currency = choice

        # Convert all amounts to display currency
        portfolio = {}
        for ticker in entries:
            amount, ccy = entries[ticker]
            portfolio[ticker] = convert_amount(amount, ccy, display_currency)

        decomposed, unknown = decompose_portfolio(portfolio)
        sectors = breakdown_by_sector(decomposed)
        countries = breakdown_by_country(decomposed)
        print_report(entries, portfolio, decomposed, sectors, countries, unknown, display_currency)
