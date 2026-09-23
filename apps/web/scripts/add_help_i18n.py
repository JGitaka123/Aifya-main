"""One-shot helper: merge tour + tooltip i18n keys into en.json and sw.json.

Run from apps/web:  python scripts/add_help_i18n.py
"""
import json
from collections import OrderedDict
from pathlib import Path

EN_ADDITIONS = {
    "helpBot": {
        "takeTheTour": "Take a quick tour",
    },
    "tour": {
        "controls": {
            "next": "Next",
            "previous": "Back",
            "done": "Done",
            "progress": "Step {{current}} of {{total}}",
        },
        "tours": {
            "welcome": {"label": "Welcome tour"},
            "finance": {"label": "Finance tour"},
            "payroll": {"label": "Payroll tour"},
            "clinical": {"label": "Clinical tour"},
        },
        "steps": {
            "welcome": {
                "sidebar": {
                    "title": "Welcome to Aifya",
                    "description": "This is your main navigation. All hospital modules are listed here. Click any item to jump to that area.",
                },
                "helpBot": {
                    "title": "Need help anytime?",
                    "description": "Click this button to ask the AI assistant any 'how do I' question. It can also point you to the right page.",
                },
                "themeToggle": {
                    "title": "Light or dark mode",
                    "description": "Switch between light and dark themes here. Aifya remembers your choice.",
                },
                "userMenu": {
                    "title": "Your account",
                    "description": "Sign out, change your password, and access account settings from here.",
                },
            },
            "finance": {
                "dashboard": {
                    "title": "Finance Dashboard",
                    "description": "See total cash, net profit, AR balance and AP at a glance. Reports update automatically as transactions post.",
                },
                "billing": {
                    "title": "Billing and Invoices",
                    "description": "Create invoices and record payments. Each invoice automatically posts a balanced double-entry journal to the General Ledger.",
                },
                "reports": {
                    "title": "Financial Reports",
                    "description": "P&L, Balance Sheet, Cash Flow, Trial Balance, AR Aging, Budget vs Actual all derived live from transactions.",
                },
                "helpBot": {
                    "title": "Stuck on accounting?",
                    "description": "Aifya handles all double-entry posting automatically. Ask the AI helper if anything looks unfamiliar.",
                },
            },
            "payroll": {
                "dashboard": {
                    "title": "Payroll Dashboard",
                    "description": "See monthly headcount, gross pay, PAYE, and net pay. Current month status is shown at the top.",
                },
                "employees": {
                    "title": "Employee Records",
                    "description": "Add and edit staff. Every employee needs a KRA PIN, NSSF number, SHIF number and bank account before payroll can run.",
                },
                "leave": {
                    "title": "Leave Management",
                    "description": "Approve annual, sick, maternity and other leave types. Unpaid leave automatically reduces net pay.",
                },
                "reports": {
                    "title": "Payroll Reports",
                    "description": "Monthly summaries, P9 returns, KRA P10 schedules, NSSF and SHIF reports.",
                },
                "statutory": {
                    "title": "Statutory Rates",
                    "description": "PAYE bands, NSSF tiers, SHIF and Housing Levy all configurable here. No code changes when KRA updates rates.",
                },
            },
            "clinical": {
                "patients": {
                    "title": "Patient Records",
                    "description": "Search and register patients. Aifya works fully offline and syncs when reconnected.",
                },
                "opd": {
                    "title": "Outpatient Department",
                    "description": "View today's queue, start consultations, record vitals and diagnoses, prescribe drugs, order labs.",
                },
                "ipd": {
                    "title": "Inpatient Department",
                    "description": "Admissions, ward and bed management, nursing notes, discharge summaries.",
                },
                "emergency": {
                    "title": "Emergency",
                    "description": "Triage (ESI/KTAS), rapid assessment and disposition. Critical patients can skip the queue.",
                },
                "laboratory": {
                    "title": "Laboratory",
                    "description": "Lab orders, specimen tracking, result entry. Critical values trigger immediate alerts.",
                },
                "pharmacy": {
                    "title": "Pharmacy",
                    "description": "Dispense prescriptions and manage stock. Drug interactions are checked before dispensing.",
                },
            },
        },
    },
    "patients": {
        "help": {
            "nationalId": "Optional. The patient's Kenyan National ID (8 digits). Useful for SHA verification but not required.",
            "phoneNumber": "Required. Format: 07XX XXX XXX or +2547XX XXX XXX. Used for appointment reminders and M-Pesa.",
        },
    },
    "payroll": {
        "help": {
            "kraPin": "Format: A123456789B (1 letter + 9 digits + 1 letter, 11 chars total). Required by KRA for PAYE filing.",
            "nssfNumber": "The employee's NSSF member number. Required for monthly Tier I and II contributions (max KSh 6,480/mo).",
            "shifNumber": "Social Health Insurance Fund number (replaced NHIF Oct 2024). Format example: CR1620021837701-1.",
            "disabilityExemption": "Tick if employee has registered disability. They get KSh 150,000/month tax exemption.",
        },
    },
    "finance": {
        "help": {
            "accountCode": "Numeric code, e.g. 1001 (Cash), 4001 (Consultation Income). 1xxx=Assets, 2xxx=Liabilities, 3xxx=Equity, 4xxx=Income, 5xxx=Expenses.",
            "accountType": "Asset = what you own. Liability = what you owe. Equity = capital and retained earnings. Income = revenue. Expense = costs.",
            "cashflowCategory": "Operating = day-to-day. Investing = equipment / fixed assets. Financing = loans, capital. None = equity.",
        },
    },
}

SW_ADDITIONS = {
    "helpBot": {
        "takeTheTour": "Pata utangulizi mfupi",
    },
    "tour": {
        "controls": {
            "next": "Endelea",
            "previous": "Rudi",
            "done": "Mwisho",
            "progress": "Hatua {{current}} kati ya {{total}}",
        },
        "tours": {
            "welcome": {"label": "Utangulizi"},
            "finance": {"label": "Utangulizi wa Fedha"},
            "payroll": {"label": "Utangulizi wa Mishahara"},
            "clinical": {"label": "Utangulizi wa Kliniki"},
        },
        "steps": {
            "welcome": {
                "sidebar": {
                    "title": "Karibu Aifya",
                    "description": "Hii ndiyo orodha kuu ya urambazaji. Vifaa vyote vya hospitali viko hapa. Bonyeza kufungua sehemu yoyote.",
                },
                "helpBot": {
                    "title": "Unahitaji msaada?",
                    "description": "Bonyeza kitufe hiki kuuliza msaidizi wa AI swali lolote. Anaweza pia kukuelekeza ukurasa sahihi.",
                },
                "themeToggle": {
                    "title": "Mwangaza au giza",
                    "description": "Badilisha kati ya mwangaza na giza hapa. Aifya itakumbuka chaguo lako.",
                },
                "userMenu": {
                    "title": "Akaunti yako",
                    "description": "Toka, badilisha nenosiri, na fikia mipangilio ya akaunti hapa.",
                },
            },
            "finance": {
                "dashboard": {
                    "title": "Dashibodi ya Fedha",
                    "description": "Ona pesa zote, faida halisi, AR na AP kwa muhtasari. Ripoti zinasasishwa moja kwa moja.",
                },
                "billing": {
                    "title": "Bili na Risiti",
                    "description": "Tengeneza bili, rekodi malipo. Kila bili huingiza moja kwa moja jarida la kuingia mara mbili kwenye Leja Kuu.",
                },
                "reports": {
                    "title": "Ripoti za Kifedha",
                    "description": "P&L, Mizani, Mtiririko wa Pesa na zaidi vyote vinatengenezwa moja kwa moja kutoka kwa miamala.",
                },
                "helpBot": {
                    "title": "Umekwama na uhasibu?",
                    "description": "Aifya inashughulikia uingizaji wote wa kuingia mara mbili moja kwa moja. Uliza msaidizi wa AI ikiwa kitu hakikielewi.",
                },
            },
            "payroll": {
                "dashboard": {
                    "title": "Dashibodi ya Mishahara",
                    "description": "Ona idadi ya wafanyakazi, jumla ya mshahara, PAYE na mshahara halisi.",
                },
                "employees": {
                    "title": "Kumbukumbu za Wafanyakazi",
                    "description": "Ongeza na hariri wafanyakazi. Kila mfanyakazi anahitaji KRA PIN, NSSF na SHIF kabla ya mshahara.",
                },
                "leave": {
                    "title": "Usimamizi wa Likizo",
                    "description": "Idhinisha likizo. Likizo isiyolipwa hupunguza mshahara halisi moja kwa moja.",
                },
                "reports": {
                    "title": "Ripoti za Mishahara",
                    "description": "Muhtasari wa kila mwezi, P9, ratiba za KRA P10, ripoti za NSSF na SHIF.",
                },
                "statutory": {
                    "title": "Viwango vya Kisheria",
                    "description": "Vipande vya PAYE, NSSF, SHIF na Tozo la Nyumba vyote vinaweza kubadilishwa hapa.",
                },
            },
            "clinical": {
                "patients": {
                    "title": "Kumbukumbu za Wagonjwa",
                    "description": "Tafuta na sajili wagonjwa. Aifya hufanya kazi bila mtandao na husawazisha unapounganisha tena.",
                },
                "opd": {
                    "title": "Idara ya Wagonjwa wa Nje",
                    "description": "Angalia foleni ya leo, anza ushauri, rekodi vital signs, agiza dawa, agiza maabara.",
                },
                "ipd": {
                    "title": "Idara ya Wagonjwa wa Ndani",
                    "description": "Kulazwa, usimamizi wa wadi na vitanda, maelezo ya wauguzi, muhtasari wa kuachiliwa.",
                },
                "emergency": {
                    "title": "Dharura",
                    "description": "Triaji (ESI/KTAS), tathmini ya haraka na uamuzi. Wagonjwa wa hatari wanaweza kuruka foleni.",
                },
                "laboratory": {
                    "title": "Maabara",
                    "description": "Maagizo ya maabara, ufuatiliaji wa sampuli, kuingiza matokeo. Maadili muhimu hutuma tahadhari.",
                },
                "pharmacy": {
                    "title": "Famasia",
                    "description": "Toa dawa, simamia stoo. Mwingiliano wa dawa unakaguliwa kabla ya kutoa.",
                },
            },
        },
    },
    "patients": {
        "help": {
            "nationalId": "Si lazima. Kitambulisho cha Kenya (tarakimu 8). Inasaidia uthibitisho wa SHA.",
            "phoneNumber": "Lazima. Muundo: 07XX XXX XXX au +2547XX XXX XXX. Inatumika kwa ukumbusho wa miadi na M-Pesa.",
        },
    },
    "payroll": {
        "help": {
            "kraPin": "Muundo: A123456789B (herufi 1 + tarakimu 9 + herufi 1). Inahitajika na KRA kwa PAYE.",
            "nssfNumber": "Nambari ya mwanachama wa NSSF. Inahitajika kwa michango ya kila mwezi (kiwango cha juu KSh 6,480/mwezi).",
            "shifNumber": "Nambari ya Mfuko wa Bima ya Afya ya Jamii (ilibadilisha NHIF Oktoba 2024). Mfano: CR1620021837701-1.",
            "disabilityExemption": "Weka tiki kama mfanyakazi ana ulemavu uliosajiliwa. Anapata msamaha wa kodi wa KSh 150,000/mwezi.",
        },
    },
    "finance": {
        "help": {
            "accountCode": "Msimbo wa nambari, mfano 1001 (Pesa), 4001 (Mapato). 1xxx=Mali, 2xxx=Madeni, 3xxx=Mtaji, 4xxx=Mapato, 5xxx=Matumizi.",
            "accountType": "Mali = unayomiliki. Madeni = unayodaiwa. Mtaji = mtaji na faida. Mapato = mapato. Matumizi = gharama.",
            "cashflowCategory": "Uendeshaji = kila siku. Uwekezaji = vifaa. Ufadhili = mikopo. Hakuna = mtaji.",
        },
    },
}


def deep_merge(target: dict, source: dict) -> dict:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            deep_merge(target[k], v)
        else:
            target[k] = v
    return target


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    for relpath, additions in [
        ("src/messages/en.json", EN_ADDITIONS),
        ("src/messages/sw.json", SW_ADDITIONS),
    ]:
        path = here / relpath
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh, object_pairs_hook=OrderedDict)
        deep_merge(data, additions)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"Updated {path}")
    print("Done")


if __name__ == "__main__":
    main()
