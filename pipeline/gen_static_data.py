"""
Generate static content for every F&O stock:
  - data/valuechain/<SYM>.json   (inputs/outputs value-chain tree)
  - data/profiles/<SYM>.json     (business profile + macro sensitivity)

Run once; commit output to repo so GitHub Pages serves it.
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VC_DIR   = ROOT / "data" / "valuechain"
PROF_DIR = ROOT / "data" / "profiles"
VC_DIR.mkdir(parents=True, exist_ok=True)
PROF_DIR.mkdir(parents=True, exist_ok=True)

# ── read stock universe ──────────────────────────────────────────────────────
with open(ROOT / "data" / "sectors.csv") as f:
    STOCKS = {r["sym"]: r for r in csv.DictReader(f)}

# ── helpers ──────────────────────────────────────────────────────────────────
def inp(name, weight=None, driver=None, fno=None, other=None, children=None):
    d = {"name": name}
    if weight:   d["weight"]   = weight
    if driver:   d["driver"]   = driver
    if fno:      d["fno"]      = fno
    if other:    d["other"]    = other
    if children: d["children"] = children
    return d

def out(name, weight=None, driver=None, fno=None, other=None, children=None):
    return inp(name, weight, driver, fno, other, children)

def vc(sym, inputs, outputs, note="Draft – verify against annual reports and earnings calls."):
    return {"sym": sym, "status": "draft", "note": note, "inputs": inputs, "outputs": outputs}

def profile(sym, name, what, segments, drivers, macro):
    """
    what     : 1-line description
    segments : list of {name, pct_rev (optional), note}
    drivers  : list of key earnings drivers (strings)
    macro    : list of {factor, direction, note}  e.g. {factor:"Crude oil", direction:"negative"}
    """
    return {"sym": sym, "name": name, "what": what,
            "segments": segments, "earnings_drivers": drivers, "macro_sensitivity": macro}

# ── value-chain definitions ───────────────────────────────────────────────────
# Grouped by sector for readability. Already done: MARUTI (loaded from file).

VALUECHAIN = {}

# ── BANKING (20 stocks) ──────────────────────────────────────────────────────
_bank_inputs = [
    inp("Deposits (cost of funds)", "High", "RBI repo rate, liquidity",
        children=[inp("CASA deposits", driver="Savings rate"), inp("Term deposits", driver="FD rates"), inp("Borrowings / bonds", driver="G-sec yields")]),
    inp("Technology and infrastructure", "Medium", driver="USD/INR on import",
        other=["Infosys","TCS","Wipro – core banking"], fno=["INFY","TCS","WIPRO"]),
    inp("Employee costs", "High"),
    inp("Provisions and credit costs", "High", driver="Credit cycle, NPAs"),
]
_bank_outputs = [
    out("Retail loans", "Largest", "Home/auto loan rates, credit demand",
        children=[out("Home loans"), out("Auto loans"), out("Personal loans"), out("Credit cards", fno=["SBICARD"])]),
    out("Corporate and SME loans", "Large"),
    out("Treasury (bonds, forex)", driver="G-sec yields, USD/INR"),
    out("Fees and commissions", driver="Transaction volumes"),
    out("Insurance and wealth distribution", fno=["HDFCLIFE","SBILIFE","ICICIGI"]),
]
for sym in ["AXISBANK","BANDHANBNK","BANKBARODA","BANKINDIA","CANBK","FEDERALBNK",
            "HDFCBANK","ICICIBANK","IDFCFIRSTB","INDIANB","INDUSINDBK","KOTAKBANK",
            "MAHABANK","PNB","RBLBANK","SBIN","UJJIVANSFB","UNIONBANK","YESBANK","AUBANK"]:
    VALUECHAIN[sym] = vc(sym, _bank_inputs, _bank_outputs)

# ── NBFC / FINANCE ───────────────────────────────────────────────────────────
_nbfc_inputs = [
    inp("Cost of borrowing", "High", "RBI repo, credit rating, G-sec yields",
        children=[inp("NCD / bond issuances"), inp("Bank borrowings"), inp("Commercial paper")]),
    inp("Employee costs"),
    inp("Technology", fno=["INFY","TCS"]),
    inp("Credit costs / provisions", "High", driver="Collection efficiency, delinquency"),
]
_nbfc_outputs = [
    out("Consumer loans", driver="Interest rates, consumption demand",
        children=[out("Two-wheeler / auto loans"), out("Personal loans"), out("Microfinance"), out("Consumer durables")]),
    out("SME / business loans"),
    out("Gold loans", driver="Gold price", fno=["MUTHOOTFIN","MANAPPURAM"]),
    out("Insurance and investment products", fno=["BAJAJFINSV"]),
]
for sym in ["BAJFINANCE","BAJAJFINSV","CHOLAFIN","LTF","LICHSGFIN","MANAPPURAM",
            "MUTHOOTFIN","PNBHOUSING","SHRIRAMFIN","JIOFIN","ANANDRATHI"]:
    VALUECHAIN[sym] = vc(sym, _nbfc_inputs, _nbfc_outputs)

# ── INSURANCE ────────────────────────────────────────────────────────────────
_ins_inputs = [
    inp("Claims (life / health / general)", "High", driver="Mortality tables, medical inflation"),
    inp("Investment portfolio", driver="Equity markets, G-sec yields"),
    inp("Reinsurance costs"),
    inp("Agent and distribution costs"),
]
_ins_outputs = [
    out("Life insurance premiums", "Largest", driver="Household savings rate"),
    out("Health insurance premiums", driver="Medical inflation"),
    out("General insurance premiums"),
    out("Investment income", driver="Equity + bond markets"),
    out("Annuity and pension products"),
]
for sym in ["HDFCLIFE","ICICILIFE","ICICIGI","LICI","MFSL","SBILIFE"]:
    VALUECHAIN[sym] = vc(sym, _ins_inputs, _ins_outputs)

# ── CAPITAL MARKETS / BROKING ────────────────────────────────────────────────
_broker_inputs = [
    inp("Technology platform", fno=["INFY","TCS","COFORGE"]),
    inp("Exchange fees and STT"),
    inp("Employee costs"),
    inp("Clearing and settlement costs"),
]
_broker_outputs = [
    out("Broking commissions / fees", "Largest", driver="Market volumes, F&O activity"),
    out("Asset management fees", driver="AUM, equity markets"),
    out("Distribution commissions", fno=["HDFCAMC","NAM-INDIA"]),
    out("Investment banking fees"),
    out("Margin funding income"),
]
for sym in ["360ONE","ANGELONE","BSE","CAMS","CDSL","KFINTECH","MCX","MOTILALOFS","NAUKRI","NAM-INDIA","HDFCAMC"]:
    VALUECHAIN[sym] = vc(sym, _broker_inputs, _broker_outputs)

# ── IT SERVICES ───────────────────────────────────────────────────────────────
_it_inputs = [
    inp("Employees (talent)", "Highest", driver="Wage inflation, attrition, tier-1 campus hiring"),
    inp("Cloud and infrastructure", driver="USD cost", other=["AWS","Azure","GCP"]),
    inp("Software licences and tools"),
    inp("Office space / facilities"),
]
_it_outputs = [
    out("IT services and outsourcing", "Largest", driver="USD/INR, global IT spend",
        children=[out("BFSI vertical"), out("Retail and CPG"), out("Manufacturing"), out("Healthcare"), out("Energy and utilities")]),
    out("Digital / cloud projects", driver="Enterprise digital budgets"),
    out("Products and platforms"),
    out("BPO / BPS"),
]
for sym in ["COFORGE","HCLTECH","INFY","KPITTECH","LTM","MPHASIS","OFSS","PERSISTENT","TCS","TECHM","WIPRO"]:
    VALUECHAIN[sym] = vc(sym, _it_inputs, _it_outputs)

# ── AUTOMOBILE ───────────────────────────────────────────────────────────────
# MARUTI already has a detailed file - skip here, handled by existing JSON
_auto_inputs = [
    inp("Steel and metals", "High", "India HRC/CRC, LME aluminium",
        fno=["TATASTEEL","JSWSTEEL","SAIL","HINDALCO"]),
    inp("Bought-out components", "High", driver="Steel and rubber pass-through",
        fno=["BHARATFORG","SONACOMS","BOSCHLTD","MOTHERSON","UNOMINDA","TIINDIA"]),
    inp("Tyres", driver="Natural rubber, crude", other=["MRF","Apollo Tyres","CEAT"]),
    inp("Plastics and rubber", driver="Crude, naphtha", fno=["RELIANCE"]),
    inp("Electronics and semiconductors", driver="Global semicon supply"),
    inp("Energy", driver="Gas and power tariffs", fno=["GAIL","NTPC"]),
    inp("Logistics", fno=["CONCOR","DELHIVERY"]),
]
_auto_outputs = [
    out("Domestic vehicles", "Largest", driver="Rural income, festive demand, fuel price, loan rates"),
    out("Exports", driver="USD/INR, emerging market demand"),
    out("Spare parts", "High margin"),
    out("Servicing and repairs"),
    out("Finance / insurance tie-ups", fno=["BAJFINANCE","HDFCBANK","ICICIGI"]),
]
for sym in ["ASHOKLEY","BAJAJ-AUTO","EICHERMOT","HEROMOTOCO","HYUNDAI","M_M","TVSMOTOR"]:
    VALUECHAIN[sym] = vc(sym, _auto_inputs, _auto_outputs)

# Auto ancillaries
_autoanc_inputs = [
    inp("Steel / aluminium", "High", fno=["TATASTEEL","JSWSTEEL","HINDALCO"]),
    inp("Rubber and polymers", driver="Crude, natural rubber", fno=["RELIANCE"]),
    inp("Electronic components", driver="Semiconductor supply"),
    inp("Energy", fno=["NTPC","TATAPOWER"]),
]
_autoanc_outputs = [
    out("OEM supply to auto manufacturers", "Largest",
        fno=["MARUTI","M_M","TATAMOTORS" if "TATAMOTORS" in STOCKS else "TVSMOTOR","BAJAJ-AUTO"]),
    out("Aftermarket / spare parts", driver="Replacement cycle"),
    out("Exports", driver="USD/INR"),
]
for sym in ["BHARATFORG","BOSCHLTD","MOTHERSON","SONACOMS","TIINDIA","UNOMINDA","FORCEMOT","CROMPTON"]:
    VALUECHAIN[sym] = vc(sym, _autoanc_inputs, _autoanc_outputs)

# ── HEALTHCARE / PHARMA ───────────────────────────────────────────────────────
_pharma_inputs = [
    inp("Active Pharmaceutical Ingredients (APIs)", "High", driver="China API prices, USD/INR",
        other=["Imported APIs from China","Domestic API manufacturers"]),
    inp("Solvents and excipients", driver="Crude and chemical prices"),
    inp("Packaging materials", driver="Plastic and aluminium prices"),
    inp("R&D costs", driver="Clinical trial spend"),
    inp("Energy", fno=["NTPC","TATAPOWER"]),
]
_pharma_outputs = [
    out("Generics (US market)", "Largest for most", driver="USFDA approvals, USD/INR, pricing pressure"),
    out("Domestic branded generics", driver="India pharma market growth"),
    out("Active Pharmaceuticals (API sales)"),
    out("Specialty and complex generics"),
    out("Hospital / institutional supply", fno=["APOLLOHOSP","FORTIS","MAXHEALTH"]),
]
for sym in ["ALKEM","AUROPHARMA","BIOCON","CIPLA","DIVISLAB","DRREDDY","GLENMARK",
            "LAURUSLABS","LUPIN","MANKIND","SUNPHARMA","TORNTPHARM","ZYDUSLIFE","PIIND"]:
    VALUECHAIN[sym] = vc(sym, _pharma_inputs, _pharma_outputs)

_hospital_inputs = [
    inp("Medical consumables and devices", driver="USD/INR on imports"),
    inp("Drugs and pharmaceuticals", fno=["SUNPHARMA","CIPLA","DRREDDY"]),
    inp("Employee costs (doctors, nurses)", "Highest"),
    inp("Real estate and capex"),
]
_hospital_outputs = [
    out("In-patient services (IPD)", "Largest", driver="ARPU, occupancy"),
    out("Out-patient services (OPD)"),
    out("Diagnostics"),
    out("Pharmacy retail", fno=["SUNPHARMA"]),
    out("Health insurance claims", fno=["ICICIGI","HDFCLIFE"]),
]
for sym in ["APOLLOHOSP","FORTIS","MAXHEALTH"]:
    VALUECHAIN[sym] = vc(sym, _hospital_inputs, _hospital_outputs)

# ── FMCG ──────────────────────────────────────────────────────────────────────
_fmcg_inputs = [
    inp("Agricultural commodities", "High", driver="Monsoon, commodity cycles",
        children=[inp("Palm oil / edible oils", driver="Malaysia CPO price"),
                  inp("Wheat and grains"),
                  inp("Sugar", driver="Domestic sugar price"),
                  inp("Milk solids", driver="Milk procurement price")]),
    inp("Crude derivatives (packaging, chemicals)", driver="Crude oil price", fno=["RELIANCE"]),
    inp("Packaging materials", driver="Aluminium, paper prices"),
    inp("Advertising and promotion", "High"),
    inp("Distribution network"),
]
_fmcg_outputs = [
    out("Home care products"),
    out("Personal care and beauty"),
    out("Foods and beverages"),
    out("Nutrition and health"),
    out("OTC healthcare"),
]
for sym in ["BRITANNIA","COLPAL","DABUR","GODREJCP","HINDUNILVR","ITC","MARICO","NESTLEIND","TATACONSUM"]:
    VALUECHAIN[sym] = vc(sym, _fmcg_inputs, _fmcg_outputs)

# ── CAPITAL GOODS / INDUSTRIALS ───────────────────────────────────────────────
_capgoods_inputs = [
    inp("Steel and metals", "High", fno=["TATASTEEL","JSWSTEEL","HINDALCO"]),
    inp("Electrical components", driver="Copper prices", fno=["HINDALCO","VEDL"]),
    inp("Electronic components", driver="Semiconductor supply"),
    inp("Contract manufacturing", fno=["DIXON","AMBER"]),
    inp("Energy", fno=["NTPC","TATAPOWER"]),
]
_capgoods_outputs = [
    out("Power equipment / transformers", driver="Power capex, infrastructure spend"),
    out("Industrial automation"),
    out("Railway and defence equipment", driver="Govt capex budget"),
    out("Engineering project orders", driver="Order inflows"),
    out("After-sales service"),
]
for sym in ["ABB","BHEL","CUMMINSIND","HAL","HAVELLS","L&T" if "L&T" in STOCKS else "LT",
            "LT","SIEMENS","THERMAX" if "THERMAX" in STOCKS else "BDL","BDL","BEL",
            "CGPOWER","COCHINSHIP","MAZDOCK","POWERINDIA"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _capgoods_inputs, _capgoods_outputs)

# ── POWER ─────────────────────────────────────────────────────────────────────
_power_inputs = [
    inp("Coal", "Highest for thermal", driver="Coal India supply, import coal price",
        fno=["COALINDIA"]),
    inp("Gas", driver="LNG spot, APM gas price", fno=["GAIL","PETRONET"]),
    inp("Solar panels / wind equipment", driver="Module prices, USD/INR"),
    inp("Equipment and EPC", fno=["BHEL","ABB","SIEMENS","LT"]),
    inp("Land and transmission infrastructure"),
]
_power_outputs = [
    out("Electricity generation (units)", "Largest", driver="PLF, power tariffs, PPA rates"),
    out("Renewable energy", driver="Solar/wind tariff, RPO mandates"),
    out("Transmission and distribution"),
    out("Green hydrogen / carbon credits", driver="Policy, global carbon price"),
]
for sym in ["ADANIGREEN","ADANIPOWER","INOXWIND","IREDA","JSWENERGY","NHPC","NTPC",
            "POWERGRID","SJVN" if "SJVN" in STOCKS else "TATAPOWER","SUZLON","TATAPOWER","WAAREEENER"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _power_inputs, _power_outputs)

# ── OIL AND GAS / CRUDE ───────────────────────────────────────────────────────
_oil_upstream = [
    inp("Exploration and drilling capex", driver="Crude price justification"),
    inp("Oilfield services", driver="Day rates, steel"),
    inp("Equipment and chemicals"),
]
_oil_upstream_out = [
    out("Crude oil", "Largest", driver="Brent crude price, OPEC output"),
    out("Natural gas", driver="Gas APM price"),
    out("Petrochemicals", fno=["RELIANCE"]),
    out("Refining (for integrated players)", driver="GRM – gross refining margin"),
]
for sym in ["BPCL","GAIL","HINDPETRO","IOC","OIL","ONGC","PETRONET","RELIANCE"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _oil_upstream, _oil_upstream_out)

# ── METALS ────────────────────────────────────────────────────────────────────
_steel_inputs = [
    inp("Iron ore", "High", driver="Seaborne iron ore price", other=["NMDC"], fno=["NMDC"]),
    inp("Coking coal", "High", driver="Australian coking coal price (imported)"),
    inp("Scrap steel", driver="Global scrap price"),
    inp("Energy (electricity, gas)", driver="Power tariff, gas prices", fno=["NTPC","GAIL"]),
    inp("Logistics", fno=["CONCOR"]),
]
_steel_outputs = [
    out("Hot-rolled coil / flat steel", "Largest", driver="China steel export, domestic demand",
        fno=["MARUTI","L&T" if "L&T" in STOCKS else "LT","BHEL"]),
    out("Long products (rebars, wire rods)", driver="Construction activity"),
    out("Specialty steel", driver="Auto, defence demand"),
    out("Downstream (pipes, tubes)", fno=["APLAPOLLO"]),
]
for sym in ["JINDALSTEL","JSWSTEEL","SAIL","TATASTEEL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _steel_inputs, _steel_outputs)

_aluminium_inputs = [
    inp("Bauxite and alumina", "High", driver="Bauxite availability"),
    inp("Coal and power", "Very High", driver="Power cost per tonne is ~40% of cost", fno=["COALINDIA","NTPC"]),
    inp("Caustic soda", driver="Chlor-alkali prices"),
]
_aluminium_outputs = [
    out("Primary aluminium", "Largest", driver="LME aluminium, China production"),
    out("Value-added products (rods, sheets, foils)"),
    out("Copper (Hindalco also smelts copper)", driver="LME copper"),
]
for sym in ["HINDALCO","NATIONALUM","VEDL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _aluminium_inputs, _aluminium_outputs)

for sym in ["COALINDIA","NMDC"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Mining operations", driver="Royalties, overburden removal"), inp("Logistics", fno=["CONCOR"]), inp("Equipment")],
            [out("Coal / iron ore", "Largest", driver="Coal India notified price / international iron ore price",
                 fno=["NTPC","TATAPOWER","TATASTEEL","JSWSTEEL"]),
             out("Coking coal (NMDC steel plant)"),
             out("Pellets and sinter (NMDC)")]
        )

# ── CEMENT ────────────────────────────────────────────────────────────────────
_cement_inputs = [
    inp("Limestone (captive quarry)", "Medium"),
    inp("Coal and pet coke", "High", driver="Global coal price", fno=["COALINDIA"]),
    inp("Power and fuel", "High", driver="Power tariff, solar capex"),
    inp("Logistics", "Medium", driver="Diesel price", fno=["CONCOR"]),
    inp("Fly ash and slag", driver="Proximity to thermal plants"),
]
_cement_outputs = [
    out("Cement (OPC, PPC, PSC)", "Largest", driver="Infrastructure and housing activity, regional pricing"),
    out("Ready-mix concrete"),
    out("Building products"),
]
for sym in ["AMBUJACEM","SHREECEM","ULTRACEMCO"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _cement_inputs, _cement_outputs)

# ── REALTY ────────────────────────────────────────────────────────────────────
_realty_inputs = [
    inp("Land", "High", driver="Land price inflation"),
    inp("Construction materials", driver="Steel, cement prices", fno=["TATASTEEL","ULTRACEMCO"]),
    inp("Labour", driver="Wage inflation"),
    inp("Home loan offtake", driver="Interest rates", fno=["HDFCBANK","SBIN","LICHSGFIN"]),
]
_realty_outputs = [
    out("Residential launches and bookings", "Largest", driver="Housing demand, affordability"),
    out("Commercial leasing", driver="IT and BFSI office demand"),
    out("Retail malls", driver="Consumer footfall, retailer expansion"),
    out("Hospitality", fno=["INDHOTEL"]),
]
for sym in ["DLF","GODREJPROP","LODHA","OBEROIRLTY","PHOENIXLTD","PRESTIGE"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _realty_inputs, _realty_outputs)

# ── TELECOM ───────────────────────────────────────────────────────────────────
_telecom_inputs = [
    inp("Spectrum fees and AGR dues"),
    inp("Network equipment capex", driver="USD/INR on imports", other=["Ericsson","Nokia","Samsung"]),
    inp("Power and energy", "High", fno=["NTPC","TATAPOWER"]),
    inp("Tower rental", fno=["INDUSTOWER"]),
    inp("Content and OTT deals"),
]
_telecom_outputs = [
    out("Mobile data subscriptions", "Largest", driver="ARPU, subscriber adds, 5G monetisation"),
    out("Voice and SMS"),
    out("Enterprise connectivity"),
    out("Homes broadband (Jio/Airtel)"),
    out("Digital services and OTT"),
]
for sym in ["BHARTIARTL","IDEA","INDUSTOWER"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _telecom_inputs, _telecom_outputs)

# ── CONSUMER DURABLES / ELECTRONICS ──────────────────────────────────────────
_ce_inputs = [
    inp("Electronic components", "High", driver="Semicon supply, USD/INR", other=["Imported from China/Korea"]),
    inp("Steel and metals", fno=["TATASTEEL","HINDALCO"]),
    inp("Plastics", driver="Crude price", fno=["RELIANCE"]),
    inp("Contract manufacturing", fno=["DIXON","AMBER"]),
]
_ce_outputs = [
    out("Consumer electronics (TVs, appliances)", "Largest", driver="Consumer discretionary spend, urban demand"),
    out("Lighting and switchgear"),
    out("Air conditioners and refrigerators", driver="Summer heat intensity, real estate"),
    out("Small appliances"),
]
for sym in ["AMBER","BLUESTARCO","CROMPTON","DIXON","HAVELLS","VOLTAS"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _ce_inputs, _ce_outputs)

# ── LOGISTICS ─────────────────────────────────────────────────────────────────
_logi_inputs = [
    inp("Diesel and fuel", "High", driver="Crude oil price"),
    inp("Vehicles and containers", driver="Steel prices"),
    inp("Rail haulage", fno=["CONCOR"]),
    inp("Technology (TMS, WMS)", fno=["INFY","TCS"]),
]
_logi_outputs = [
    out("Container rail freight", "Largest for CONCOR", driver="EXIM trade volumes"),
    out("Express parcel delivery", driver="E-commerce growth", fno=["DELHIVERY"]),
    out("Supply chain and warehousing"),
    out("Cold chain"),
]
for sym in ["CONCOR","DELHIVERY"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _logi_inputs, _logi_outputs)

# ── AVIATION ──────────────────────────────────────────────────────────────────
_avia_inputs = [
    inp("Aviation turbine fuel (ATF)", "Highest ~35-40% of cost", driver="Crude oil price, USD/INR"),
    inp("Aircraft lease / ownership", driver="USD/INR, LIBOR"),
    inp("Airport charges", driver="Regulator-set tariffs"),
    inp("Maintenance, Repair, Overhaul (MRO)"),
    inp("Employee costs"),
]
_avia_outputs = [
    out("Domestic passenger revenue", "Largest", driver="Yield, load factor, capacity"),
    out("International routes"),
    out("Cargo", driver="E-commerce, perishables"),
    out("Ancillaries (seats, meals, hotels)"),
]
for sym in ["INDIGO"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _avia_inputs, _avia_outputs)

# ── RETAILING ─────────────────────────────────────────────────────────────────
_retail_inputs = [
    inp("Merchandise procurement", "High", driver="Category mix, supplier terms",
        children=[inp("Apparel and textiles", driver="Cotton prices"),
                  inp("FMCG packaged goods", fno=["HINDUNILVR","ITC","BRITANNIA"]),
                  inp("Electronics", fno=["DIXON","AMBER"]),
                  inp("General merchandise")]),
    inp("Store rentals", driver="Real estate costs", fno=["DLF","PHOENIXLTD"]),
    inp("Logistics", fno=["DELHIVERY","CONCOR"]),
    inp("Employee costs"),
    inp("Technology (ERP, e-comm)", fno=["INFY","TCS"]),
]
_retail_outputs = [
    out("Offline store sales", "Largest"),
    out("Private label brands", "High margin"),
    out("E-commerce / quick commerce"),
    out("Financial services (cards, EMI)", fno=["BAJFINANCE","SBICARD"]),
]
for sym in ["DMART","VMM","TRENT","NYKAA","ETERNAL","SWIGGY"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _retail_inputs, _retail_outputs)

# ── HOSPITALITY ───────────────────────────────────────────────────────────────
for sym in ["INDHOTEL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Food and beverage", driver="Food inflation, commodity prices"),
             inp("Employee costs", "High"),
             inp("Energy", fno=["NTPC","TATAPOWER"]),
             inp("Property and maintenance")],
            [out("Room revenue (RevPAR)", "Largest", driver="Domestic travel, corp demand, RevPAR"),
             out("Food and beverage"),
             out("Events and weddings"),
             out("Management contracts")]
        )

# ── CHEMICALS ─────────────────────────────────────────────────────────────────
_chem_inputs = [
    inp("Crude derivatives (naphtha, benzene)", "High", driver="Crude price", fno=["RELIANCE","BPCL"]),
    inp("Speciality chemicals (intermediates)", driver="China supply, anti-dumping"),
    inp("Energy", fno=["NTPC","TATAPOWER"]),
]
_chem_outputs = [
    out("Agrochemicals", "Largest for PI/UPL", driver="Monsoon, farm income", fno=["PIIND","UPL"]),
    out("Specialty chemicals for pharma", fno=["SUNPHARMA","CIPLA"]),
    out("Dyes and pigments", driver="Textile and paint demand"),
    out("Fluorochemicals", driver="Refrigerant and EV battery demand"),
]
for sym in ["PIIND","SRF","UPL","ASTRAL","GLENMARK"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _chem_inputs, _chem_outputs)

# ── PLASTICS ──────────────────────────────────────────────────────────────────
for sym in ["APLAPOLLO","SUPREMEIND"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Steel coils / polymer resin", "High", driver="HRC steel / HDPE-PVC prices",
                 fno=["TATASTEEL","JSWSTEEL","RELIANCE"]),
             inp("Energy"),
             inp("Logistics", fno=["CONCOR"])],
            [out("Steel tubes and pipes", driver="Construction, infra, oil & gas"),
             out("PVC and CPVC pipes", driver="Real estate, agri irrigation", fno=["DLF","LODHA"]),
             out("Plastic tanks and containers")]
        )

# ── CONSTRUCTION / INFRA ──────────────────────────────────────────────────────
_infra_inputs = [
    inp("Steel and rebar", "High", fno=["TATASTEEL","JSWSTEEL","SAIL"]),
    inp("Cement", "High", fno=["ULTRACEMCO","AMBUJACEM","SHREECEM"]),
    inp("Sand, aggregate and other materials"),
    inp("Equipment and machinery", fno=["LT","BHEL"]),
    inp("Labour"),
    inp("Finance", driver="Interest cost, project financing", fno=["SBIN","HDFCBANK"]),
]
_infra_outputs = [
    out("Infrastructure projects (roads, metro, ports)", "Largest", driver="Govt capex budget, NHDP"),
    out("Real estate construction", fno=["DLF","GODREJPROP","LODHA"]),
    out("Industrial and commercial buildings"),
    out("O&M contracts"),
]
for sym in ["LT","NBCC","RVNL","GMRAIRPORT"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym, _infra_inputs, _infra_outputs)

# ── SHIP BUILDING ─────────────────────────────────────────────────────────────
for sym in ["COCHINSHIP","MAZDOCK"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Steel plates", "High", fno=["TATASTEEL","JSWSTEEL"]),
             inp("Marine engines and equipment", driver="EUR/INR, USD/INR"),
             inp("Labour and skilled workers"),
             inp("Defence electronics")],
            [out("Naval vessels and defence ships", "Largest", driver="Defence capex budget"),
             out("Commercial vessels"),
             out("Ship repairs and refit")]
        )

# ── DEFENCE / AEROSPACE ───────────────────────────────────────────────────────
for sym in ["BDL","BEL","HAL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Electronics and avionics", driver="USD/INR on imports"),
             inp("Metals and composites", fno=["TATASTEEL","HINDALCO"]),
             inp("Technology licences and ToT"),
             inp("Skilled workforce")],
            [out("Defence systems and platforms", "Largest", driver="Defence capex budget, Atmanirbhar Bharat"),
             out("Exports under government deals"),
             out("After-sales and MRO")]
        )

# ── JEWELLERY ─────────────────────────────────────────────────────────────────
for sym in ["KALYANKJIL","TITAN"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Gold", "Highest", driver="MCX gold price, USD/INR"),
             inp("Diamonds and precious stones", driver="Global rough diamond prices"),
             inp("Working capital and gold loans", driver="Interest rates")],
            [out("Gold jewellery", "Largest", driver="Wedding season, rural income, gold price"),
             out("Diamond jewellery"),
             out("Watches and accessories", fno=["TITAN"]),
             out("Eyewear and fashion", fno=["TITAN"])]
        )

# ── ALCOHOL ───────────────────────────────────────────────────────────────────
for sym in ["RADICO","UNITDSPR"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Grain (ENA feedstock)", "High", driver="Wheat/barley/rice prices, monsoon"),
             inp("Glass bottles", driver="Soda ash, natural gas prices"),
             inp("Molasses and sugar", driver="Sugar price"),
             inp("Excise duties and state levies", "High")],
            [out("IMFL (whisky, rum, vodka, gin)", "Largest", driver="State govt pricing, premium mix"),
             out("Prestige and above brands", "Higher margin"),
             out("Beer (for some)"),
             out("ENA sales to other distillers")]
        )

# ── DIVERSIFIED / CONGLOMERATE ────────────────────────────────────────────────
for sym in ["ITC"]:  # ITC also FMCG but has cigarettes as the key driver
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Tobacco leaf", "High", driver="Domestic tobacco crop, state taxes"),
             inp("FMCG inputs", driver="Commodity prices for food, paper, personal care"),
             inp("Paper and packaging", driver="Wood pulp prices"),
             inp("Hotel operations inputs", driver="Food, energy")],
            [out("Cigarettes", "Largest, ~80% of profit", driver="Govt excise, taxation policy"),
             out("FMCG foods and staples"),
             out("Paperboards and packaging"),
             out("Hotels", fno=["INDHOTEL"]),
             out("Agri-business exports")]
        )

# ── MISC ──────────────────────────────────────────────────────────────────────
# Gas transmission
for sym in ["GAIL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Natural gas sourcing (LNG + domestic)", "High", driver="LNG spot, domestic APM price"),
             inp("Pipeline infrastructure"),
             inp("Energy for compression")],
            [out("Gas transmission (tolling)", "Largest", driver="Volume throughput, PNGRB tariff"),
             out("Gas trading margin"),
             out("Petrochemicals (petchem)", driver="LPG and polymer prices"),
             out("City Gas Distribution (stake in CGDs)")]
        )

# Mining - additional
for sym in ["HINDZINC"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Mining operations (zinc-lead-silver ore)", driver="Ore grade, mining costs"),
             inp("Energy – power for smelting", "High", driver="Power tariff"),
             inp("Sulphuric acid and reagents")],
            [out("Zinc metal", "Largest", driver="LME zinc price"),
             out("Lead metal", driver="LME lead"),
             out("Silver", driver="Silver price"),
             out("Sulphuric acid by-product")]
        )

for sym in ["VEDL"]:
    if sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Mining (Zn, Pb, Ag, Cu, Al, Fe ore)", driver="Ore grades, mining cost"),
             inp("Energy – smelting power", "Very High", driver="Power tariff, captive power cost"),
             inp("Coal for captive power", fno=["COALINDIA"])],
            [out("Zinc and lead", "Largest", driver="LME zinc/lead"),
             out("Aluminium", driver="LME aluminium"),
             out("Copper", driver="LME copper"),
             out("Iron ore", driver="Seaborne iron ore"),
             out("Oil and gas (Cairn India)", driver="Crude oil price")]
        )

# Fertilisers / Agri
for sym in ["UPL","PIIND"]:
    if sym not in VALUECHAIN and sym in STOCKS:
        VALUECHAIN[sym] = vc(sym,
            [inp("Technical grade pesticide (from China/BASF)", driver="Anti-dumping, USD/INR"),
             inp("Crude intermediates", driver="Crude price"),
             inp("Packaging")],
            [out("Herbicides and insecticides", driver="Monsoon, kharif/rabi acreage"),
             out("Fungicides"),
             out("Seeds (UPL)", driver="Farm income, weather"),
             out("Exports", driver="USD/INR, Latin America demand")]
        )

# FMCG missing
for sym in ["GODFRYPHLP","PAGEIND"]:
    if sym in STOCKS and sym not in VALUECHAIN:
        VALUECHAIN[sym] = vc(sym,
            [inp("Tobacco leaf / yarn", "High", driver="Tobacco price / cotton yarn price"),
             inp("Packaging", driver="Crude price")],
            [out("Cigarettes / innerwear", "Largest", driver="Excise policy / premium consumption"),
             out("Other FMCG / hosiery")]
        )

# Electrical / cables
for sym in ["KEI","POLYCAB","SUPREMEIND"]:
    if sym in STOCKS and sym not in VALUECHAIN:
        VALUECHAIN[sym] = vc(sym,
            [inp("Copper and aluminium", "High", driver="LME copper/aluminium", fno=["HINDALCO","VEDL"]),
             inp("PVC and polymers", driver="Crude, naphtha", fno=["RELIANCE"]),
             inp("Energy")],
            [out("Wires and cables", "Largest", driver="Infra spend, real estate, industrials"),
             out("Fast Moving Electrical Goods (FMEG)", driver="Consumer discretionary"),
             out("EPC projects")]
        )

# Remaining stocks not yet covered – give them a generic template
for sym in STOCKS:
    if sym not in VALUECHAIN:
        s = STOCKS[sym]
        VALUECHAIN[sym] = vc(sym,
            [inp("Key raw materials / inputs", driver="Sector-specific commodity and FX drivers"),
             inp("Employee and operating costs"),
             inp("Technology and capex", driver="Interest rates, project finance")],
            [out("Primary products / services", "Largest", driver="End-market demand, pricing power"),
             out("Value-added / premium products", driver="Mix improvement"),
             out("Exports", driver="USD/INR, global demand")],
            note=f"Generic template for {s['sector']} / {s['industry']}. Needs detail from annual report and earnings calls."
        )

# ── write value-chain files ───────────────────────────────────────────────────
count = 0
for sym, data in VALUECHAIN.items():
    p = VC_DIR / f"{sym.replace('/', '_')}.json"
    p.write_text(json.dumps(data, indent=2))
    count += 1
print(f"Wrote {count} valuechain files to {VC_DIR}")

# ── PROFILES ──────────────────────────────────────────────────────────────────
# Map sectors to macro factors
MACRO = {
    "Banking":     [{"factor":"RBI repo rate","direction":"negative","note":"Higher rates compress NIMs"},
                    {"factor":"Credit growth","direction":"positive"},
                    {"factor":"NPA cycle","direction":"negative"}],
    "Finance":     [{"factor":"RBI repo rate","direction":"negative"},
                    {"factor":"Credit cycle","direction":"positive"},
                    {"factor":"Equity markets","direction":"positive","note":"Affects AUM-linked fees"}],
    "Information Technology": [{"factor":"USD/INR","direction":"positive","note":"Revenue in USD"},
                                {"factor":"US IT spend","direction":"positive"},
                                {"factor":"US recession risk","direction":"negative"}],
    "Healthcare":  [{"factor":"USFDA approvals","direction":"positive"},
                    {"factor":"USD/INR","direction":"positive","note":"US generic revenue"},
                    {"factor":"China API prices","direction":"negative"}],
    "Automobile & Ancillaries": [{"factor":"Crude oil price","direction":"negative","note":"Fuel cost hurts demand"},
                                  {"factor":"Steel price","direction":"negative","note":"Input cost"},
                                  {"factor":"Monsoon","direction":"positive","note":"Rural demand"},
                                  {"factor":"Auto loan rates","direction":"negative"}],
    "Capital Goods": [{"factor":"Govt capex budget","direction":"positive"},
                      {"factor":"Steel / commodity prices","direction":"negative","note":"Input cost"},
                      {"factor":"Interest rates","direction":"negative","note":"Project financing"}],
    "Fast Moving Consumer Goods": [{"factor":"Crude oil","direction":"negative","note":"Packaging costs"},
                                    {"factor":"Agricultural commodities","direction":"negative","note":"Input costs"},
                                    {"factor":"Monsoon","direction":"positive","note":"Rural income"},
                                    {"factor":"Inflation","direction":"mixed"}],
    "Power":       [{"factor":"Coal price","direction":"negative","note":"Fuel cost"},
                    {"factor":"Govt capex (power infra)","direction":"positive"},
                    {"factor":"Solar panel prices","direction":"negative","note":"RE capex falls"}],
    "Crude Oil":   [{"factor":"Brent crude price","direction":"positive"},
                    {"factor":"USD/INR","direction":"positive"},
                    {"factor":"Govt fuel price controls","direction":"negative"}],
    "Iron & Steel":[{"factor":"China steel exports","direction":"negative","note":"Pricing pressure"},
                    {"factor":"Coking coal price","direction":"negative"},
                    {"factor":"Iron ore price","direction":"negative"},
                    {"factor":"Domestic construction / auto demand","direction":"positive"}],
    "Realty":      [{"factor":"Home loan rates","direction":"negative"},
                    {"factor":"Steel / cement prices","direction":"negative"},
                    {"factor":"Urban income growth","direction":"positive"}],
    "Chemicals":   [{"factor":"Crude oil / naphtha","direction":"negative","note":"Feedstock"},
                    {"factor":"China chemical exports","direction":"negative","note":"Competition"},
                    {"factor":"Monsoon / farm income","direction":"positive","note":"Agrochem demand"}],
    "Retailing":   [{"factor":"Consumer confidence","direction":"positive"},
                    {"factor":"Real estate costs","direction":"negative"},
                    {"factor":"Inflation","direction":"negative","note":"Squeezes discretionary spend"}],
}

PROFILES = {}
for sym, s in STOCKS.items():
    sector = s["sector"]
    macro = MACRO.get(sector, [{"factor":"Key sector drivers","direction":"mixed"}])
    PROFILES[sym] = profile(
        sym, s["name"],
        what=f"{s['name']} operates in the {s['industry']} segment of the {s['sector']} sector.",
        segments=[{"name": "Primary business", "note": f"See annual report for revenue breakdown by segment."}],
        drivers=[f"Sector: {sector}", f"Industry: {s['industry']}", f"Market cap: {s['mcap_cat']}",
                 "Key drivers to be populated from latest earnings call and annual report."],
        macro=macro
    )

for sym, data in PROFILES.items():
    p = PROF_DIR / f"{sym.replace('/', '_')}.json"
    p.write_text(json.dumps(data, indent=2))
print(f"Wrote {len(PROFILES)} profile files to {PROF_DIR}")

# ── update market.json to list all valuechain stocks ─────────────────────────
market_path = ROOT / "site" / "data" / "market.json"
market = json.loads(market_path.read_text())
market["valuechain"] = sorted(VALUECHAIN.keys())
market_path.write_text(json.dumps(market, indent=2))
print(f"Updated market.json valuechain list: {len(market['valuechain'])} stocks")
