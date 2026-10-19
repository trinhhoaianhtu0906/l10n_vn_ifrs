from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_vn_financial_statements.models.engine import LedgerProvider, evaluate_report

FROM, TO = date(2026, 1, 1), date(2026, 6, 30)


@tagged("post_install", "-at_install")
class TestIfrs(TransactionCase):
    """VAS books with a prepaid office rent; IFRS 16 adjustments in their own journal.

    VAS:  capital 1,000,000; rent paid in advance 120, half expensed (60);
          a VAS-only doubtful debt provision of 7.
    IFRS: right-of-use asset 500 (incl. the 120 prepaid), lease liability 380;
          the VAS rent expense is reversed, depreciation 50, interest 15.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls._new_company("IFRS Test Parent")
        cls.ifrs_journal = cls._journal(cls.company, "IFRS Adjustments", "IFRS", "ifrs")
        cls.vas_journal = cls._journal(cls.company, "VAS Only", "VASO", "vas")
        c = cls.company
        cls._post(c, date(2026, 1, 2), [("112", 1_000_000), ("41111", -1_000_000)])
        cls._post(c, date(2026, 1, 5), [("2421", 120), ("112", -120)])
        cls._post(c, date(2026, 6, 30), [("6427", 60), ("2421", -60)])
        cls._post(c, date(2026, 6, 30), [("6426", 7), ("22931", -7)], cls.vas_journal)
        cls._post(c, date(2026, 1, 1), [("212", 500), ("34122", -380), ("2421", -120)], cls.ifrs_journal)
        cls._post(c, date(2026, 6, 30), [("2421", 60), ("6427", -60)], cls.ifrs_journal)
        cls._post(c, date(2026, 6, 30), [("6424", 50), ("2142", -50)], cls.ifrs_journal)
        cls._post(c, date(2026, 6, 30), [("6351", 15), ("34122", -15)], cls.ifrs_journal)

    @classmethod
    def _new_company(cls, name):
        company = cls.env["res.company"].create(
            {"name": name, "country_id": cls.env.ref("base.vn").id, "currency_id": cls.env.ref("base.VND").id}
        )
        cls.env.user.company_ids |= company
        cls.env["account.chart.template"].with_context(allowed_company_ids=[company.id]).try_loading(
            "vn", company=company, install_demo=False
        )
        return company

    @classmethod
    def _journal(cls, company, name, code, ledger):
        return cls.env["account.journal"].create(
            {"name": name, "code": code, "type": "general", "vn_ledger": ledger, "company_id": company.id}
        )

    @classmethod
    def _post(cls, company, day, items, journal=None):
        env = cls.env(context=dict(cls.env.context, allowed_company_ids=[company.id]))
        journal = journal or env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "general"), ("vn_ledger", "=", "all")], limit=1
        )
        Account = env["account.account"]
        lines = []
        for item in items:
            code, amount = item[0], item[1]
            partner = item[2] if len(item) > 2 else env["res.partner"]
            account = Account.search([("code", "=", code), ("company_ids", "in", company.id)], limit=1)
            account = account or Account.search(
                [("code", "=like", code + "%"), ("company_ids", "in", company.id)], order="code", limit=1
            )
            assert account, code
            lines.append((0, 0, {"account_id": account.id, "partner_id": partner.id, "name": code,
                                 "debit": max(amount, 0), "credit": max(-amount, 0)}))
        move = env["account.move"].create({"journal_id": journal.id, "date": day, "line_ids": lines})
        move.action_post()
        return move

    def _run(self, xmlid, ledger, provider=None):
        report = self.env.ref(xmlid)
        provider = provider or LedgerProvider(self.env, self.company, ledger=ledger)
        result = evaluate_report(report, provider, FROM, TO)
        return {item["line"].code: item["value"] for item in result["lines"]}, result["warnings"]

    def test_vas_leaves_out_ifrs_adjustments(self):
        b01, warnings = self._run("l10n_vn_financial_statements.report_b01", "vas")
        self.assertEqual(warnings, [])
        self.assertEqual(b01["225"], 0)  # no right-of-use asset under VAS
        self.assertEqual(b01["161"], 60)
        self.assertEqual(b01["136"], -7)  # the VAS-only provision is there
        self.assertEqual(b01["420b"], -67)
        b02, _w = self._run("l10n_vn_financial_statements.report_b02", "vas")
        self.assertEqual(b02["60"], -67)

    def test_ifrs_statement_of_financial_position(self):
        sfp, warnings = self._run("l10n_vn_ifrs.report_ifrs_sfp", "ifrs")
        self.assertEqual(warnings, [])
        self.assertEqual(sfp["ROU"], 450)
        self.assertEqual(sfp["OCA"], 0)  # the prepaid rent is part of the right-of-use asset
        self.assertEqual(sfp["TRC"], 0)  # the VAS-only provision is left out
        self.assertEqual(sfp["CASH"], 999_880)
        self.assertEqual(sfp["LEASENC"], 395)
        self.assertEqual(sfp["BORNC"], 0)
        self.assertEqual(sfp["RE"], -65)
        self.assertEqual(sfp["TA"], 1_000_330)
        self.assertEqual(sfp["TA"], sfp["TEL"])

    def test_ifrs_profit_or_loss(self):
        pl, warnings = self._run("l10n_vn_ifrs.report_ifrs_pl", "ifrs")
        self.assertEqual(warnings, [])
        self.assertEqual(pl["AE"], -50)
        self.assertEqual(pl["FC"], -15)
        self.assertEqual(pl["PFY"], -65)
        self.assertEqual(pl["TCI"], -65)

    def test_every_chart_account_is_mapped_in_ifrs(self):
        accounts = self.env["account.account"].with_company(self.company).search(
            [("company_ids", "in", self.company.id)]
        )
        items = []
        for i, account in enumerate(accounts.sorted("code")):
            if account.code[:1] in "56789":
                continue
            items.append((account.code, (i % 7 + 1) * 1000 * (1 if i % 2 else -1)))
        items.append(("41111", -sum(amount for _code, amount in items)))
        self._post(self.company, date(2026, 3, 31), items)
        sfp, warnings = self._run("l10n_vn_ifrs.report_ifrs_sfp", "ifrs")
        self.assertEqual(warnings, [])
        self.assertEqual(sfp["TA"], sfp["TEL"])

    def test_wizard_uses_the_report_ledger(self):
        data = self.env["vn.report.wizard"].get_dynamic_report({
            "report_id": self.env.ref("l10n_vn_ifrs.report_ifrs_sfp").id,
            "company_id": self.company.id,
            "date_from": str(FROM),
            "date_to": str(TO),
        })
        lines = self.env["vn.report.wizard.line"].browse([line["id"] for line in data["lines"]])
        values = dict(zip(lines.mapped("code"), (line["value"] for line in data["lines"]), strict=True))
        self.assertEqual(values["ROU"], 450)
        self.assertFalse(data["show_codes"])
        self.assertTrue(all(not line["code"] for line in data["lines"]))

    def test_consolidated_goodwill_is_not_amortised_under_ifrs(self):
        sub = self._new_company("IFRS Test Subsidiary")
        self._post(sub, date(2025, 6, 1), [("112", 1000), ("41111", -1000)])
        self._post(self.company, date(2025, 12, 31), [("221", 1100, sub.partner_id), ("112", -1100)])
        group = self.env["vn.consolidation.group"].create({
            "name": "IFRS Test Group",
            "parent_company_id": self.company.id,
            "member_ids": [(0, 0, {"company_id": sub.id, "method": "full", "ownership_pct": 80,
                                   "acquisition_date": date(2025, 12, 31)})],
        })
        vas, _w = self._run("l10n_vn_consolidation.report_b01_hn", "vas", group._get_provider(ledger="vas"))
        ifrs, warnings = self._run("l10n_vn_ifrs.report_ifrs_sfp_c", "ifrs", group._get_provider(ledger="ifrs"))
        self.assertEqual(warnings, [])
        # Goodwill 1,100 - 80% x 1,000 = 300; VAS amortises 300 / 120 a month.
        self.assertEqual(vas["279"], 285)
        self.assertEqual(ifrs["GW"], 300)
        self.assertEqual(ifrs["NCI"], 200)
        self.assertEqual(ifrs["TA"], ifrs["TEL"])

    def test_ifrs_adjustments_before_acquisition_change_goodwill(self):
        """IFRS 3: goodwill is measured on the net assets under IFRS at the acquisition date."""
        sub = self._new_company("IFRS Test Subsidiary 2")
        sub_ifrs = self._journal(sub, "IFRS Adjustments", "IFRS", "ifrs")
        self._post(sub, date(2025, 6, 1), [("112", 1000), ("41111", -1000)])
        # Before the acquisition, IFRS depreciation the VAS books do not have: equity -20 under IFRS.
        self._post(sub, date(2025, 7, 1), [("6424", 20), ("2142", -20)], sub_ifrs)
        self._post(self.company, date(2025, 12, 31), [("221", 1100, sub.partner_id), ("112", -1100)])
        group = self.env["vn.consolidation.group"].create({
            "name": "IFRS Test Group 2",
            "parent_company_id": self.company.id,
            "member_ids": [(0, 0, {"company_id": sub.id, "method": "full", "ownership_pct": 80,
                                   "acquisition_date": date(2025, 12, 31)})],
        })
        group.member_ids.action_take_snapshot()  # stores the VAS equity
        self.assertEqual({line.code: line.amount for line in group.member_ids.snapshot_line_ids}, {"41111": 1000})
        vas, _w = self._run("l10n_vn_consolidation.report_b01_hn", "vas", group._get_provider(ledger="vas"))
        ifrs, warnings = self._run("l10n_vn_ifrs.report_ifrs_sfp_c", "ifrs", group._get_provider(ledger="ifrs"))
        self.assertEqual(warnings, [])
        self.assertEqual(vas["279"], 285)
        # 1,100 - 80% x (1,000 - 20) = 316, not amortised.
        self.assertEqual(ifrs["GW"], 316)
        self.assertEqual(ifrs["NCI"], 196)
        self.assertEqual(ifrs["TA"], ifrs["TEL"])
