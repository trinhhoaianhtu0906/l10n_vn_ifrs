def post_init_hook(env):
    """Give every company on the Vietnamese chart a journal for its IFRS adjustments."""
    for company in env["res.company"].search([("chart_template", "=", "vn")]):
        Journal = env["account.journal"].with_company(company)
        if Journal.search_count([("company_id", "=", company.id), ("vn_ledger", "=", "ifrs")]):
            continue
        journal = Journal.create(
            {
                "name": "IFRS Adjustments",
                "code": "IFRS",
                "type": "general",
                "vn_ledger": "ifrs",
                "company_id": company.id,
            }
        )
        # The name in every installed language (e.g. "Điều chỉnh IFRS").
        for lang, _name in env["res.lang"].get_installed():
            lang_env = env(context=dict(env.context, lang=lang))
            journal.with_env(lang_env).name = lang_env._("IFRS Adjustments")
