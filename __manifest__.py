{  # noqa: B018
    "name": "Vietnam - IFRS Statements from the VAS Books",
    "version": "19.0.1.0.0",
    "summary": "IFRS statements = VAS books + IFRS adjustment journals",
    "description": """
IFRS reporting for companies that keep their statutory books under VAS.

- Journals get a ledger: "VAS and IFRS" (default), "VAS only" or
  "IFRS adjustments only". VAS statements leave the IFRS adjustment journals
  out; IFRS statements add them to the VAS figures.
- IFRS statements (IAS 1, IAS 7) mapped from the Vietnamese chart of
  accounts: statement of financial position, statement of profit or loss and
  other comprehensive income, statement of cash flows, and the consolidated
  statement of financial position and of profit or loss.
- Consolidation under IFRS does not amortise goodwill (IFRS 3, IAS 36).
- An "IFRS Adjustments" journal is created for every company on the
  Vietnamese chart when the module is installed.
""",
    "category": "Accounting/Localizations/Reporting",
    "author": "Tricasia",
    "license": "LGPL-3",
    "depends": ["l10n_vn_consolidation"],
    "data": [
        "data/vn_report_ifrs.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
