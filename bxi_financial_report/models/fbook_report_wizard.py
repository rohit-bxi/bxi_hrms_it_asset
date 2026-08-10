# -*- coding: utf-8 -*-
from odoo import models, fields, api

class FbookReportWizard(models.TransientModel):
    _name = 'fbook.report.wizard'
    _description = 'Fbook Report Wizard'

    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        required=True,
        default=lambda self: self.env.companies
    )
    @api.model
    def _get_year_selection(self):
        from datetime import date
        current_year = date.today().year
        # Generate dynamic year selections starting from 2024 to current_year + 5
        selection = []
        for y in range(2024, current_year + 6):
            fy_num = y - 2000 + 1
            selection.append((str(y), f"FY{fy_num} - {y} -{y+1}"))
        return selection

    def _get_default_year(self):
        from datetime import date
        today = date.today()
        # Default to the current fiscal year (starts April 1st)
        if today.month < 4:
            return str(today.year - 1)
        return str(today.year)

    start_financial_year = fields.Selection(
        selection='_get_year_selection',
        string='Start Financial Year',
        required=True,
        default=_get_default_year
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        required=True, 
        default=lambda self: self.env.company.currency_id
    )


    def action_submit(self):
        self.ensure_one()
        company_str_list = []
        for comp in self.company_ids:
            if comp.country_id and comp.country_id.code:
                company_str_list.append(f"{comp.name} ({comp.country_id.code.upper()})")
            else:
                company_str_list.append(comp.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'bxi_fbook_report_dashboard',
            'name': 'Financial Book',
            'context': {
                'company_ids': self.company_ids.ids,
                'company_names': ", ".join(company_str_list),
                'start_financial_year': self.start_financial_year,
                'currency_id': self.currency_id.id,
                'currency_symbol': self.currency_id.symbol or self.currency_id.name,
            }
        }

    @api.model
    def get_report_data(self, company_ids, start_financial_year, currency_id):
        if not company_ids:
            company_ids = self.env.companies.ids
        elif isinstance(company_ids, int):
            company_ids = [company_ids]

        companies = self.env['res.company'].browse(company_ids)
        # Resolve display company: prefer the root/parent company (no parent_id) among
        # selected companies. If a parent is selected, always show parent name.
        # If only child companies are selected, show the first child's name.
        parent_company = companies.filtered(lambda c: not c.parent_id)
        company = parent_company[0] if parent_company else (companies[0] if companies else self.env.company)

        def get_c_code(c):
            if c.country_id:
                return (c.country_id.country_code_3 or c.country_id.code or '').upper().strip()
            return ''

        if len(companies) == 1:
            comp = companies[0]
            c_code = get_c_code(comp)
            company_name_only = comp.name
            country_code_str = c_code
            display_company_name = f"{comp.name} ({c_code})" if c_code else comp.name
        else:
            country_codes = [get_c_code(c) for c in companies if get_c_code(c)]
            unique_country_codes = list(dict.fromkeys(country_codes))
            country_code_str = ", ".join(unique_country_codes)
            if parent_company:
                company_name_only = parent_company[0].name
                display_company_name = f"{parent_company[0].name} ({country_code_str})" if country_code_str else parent_company[0].name
            else:
                company_name_only = ", ".join(c.name for c in companies)
                display_company_name = ", ".join(f"{c.name} ({get_c_code(c)})" if get_c_code(c) else c.name for c in companies)

        target_currency = self.env['res.currency'].browse(currency_id)

        def get_rate_company(record):
            """Return the record's own company for exchange rate lookup, or fallback."""
            rec_company = getattr(record, 'company_id', False)
            return rec_company if rec_company else company


        y2_start = int(start_financial_year)
        y1_start = y2_start - 1

        from datetime import date
        today_date = date.today()
        current_fy_start = today_date.year - 1 if today_date.month < 4 else today_date.year


        # We construct dates for 2 financial years side-by-side: April 1st to March 31st.
        quarters_def = [
            # Year 1 (e.g. FY26)
            {
                'q': 'q1',
                'year': 'y1',
                'start': f'{y1_start}-04-01',
                'end': f'{y1_start}-06-30',
            },
            {
                'q': 'q2',
                'year': 'y1',
                'start': f'{y1_start}-07-01',
                'end': f'{y1_start}-09-30',
            },
            {
                'q': 'q3',
                'year': 'y1',
                'start': f'{y1_start}-10-01',
                'end': f'{y1_start}-12-31',
            },
            {
                'q': 'q4',
                'year': 'y1',
                'start': f'{y1_start + 1}-01-01',
                'end': f'{y1_start + 1}-03-31',
            },
            # Year 2 (e.g. FY27)
            {
                'q': 'q1',
                'year': 'y2',
                'start': f'{y2_start}-04-01',
                'end': f'{y2_start}-06-30',
            },
            {
                'q': 'q2',
                'year': 'y2',
                'start': f'{y2_start}-07-01',
                'end': f'{y2_start}-09-30',
            },
            {
                'q': 'q3',
                'year': 'y2',
                'start': f'{y2_start}-10-01',
                'end': f'{y2_start}-12-31',
            },
            {
                'q': 'q4',
                'year': 'y2',
                'start': f'{y2_start + 1}-01-01',
                'end': f'{y2_start + 1}-03-31',
            },
        ]

        data = {
            'y1': {'q1': {}, 'q2': {}, 'q3': {}, 'q4': {}, 'total': {}},
            'y2': {'q1': {}, 'q2': {}, 'q3': {}, 'q4': {}, 'total': {}}
        }

        # Helper function to check if an invoice is linked to a contract
        def is_linked_to_contract(inv):
            if inv.contract_id:
                if inv.contract_id.company_id and inv.contract_id.company_id.id in company_ids:
                    return True
            # Check via Many2many invoice_ids on contract model
            linked_m2m = self.env['project.contract.management'].sudo().search([
                ('invoice_ids', 'in', [inv.id]),
                ('company_id', 'in', company_ids)
            ])
            if linked_m2m:
                return True
            # Check via Sales Orders
            sale_orders = inv.line_ids.sale_line_ids.order_id
            if sale_orders:
                linked_contracts = self.env['project.contract.management'].sudo().search([
                    ('sale_order_ids', 'in', sale_orders.ids),
                    ('company_id', 'in', company_ids)
                ])
                if linked_contracts:
                    return True
            return False

        # Initial AR outstanding prior to Year 1 (posted customer invoices before y1_start with unpaid balance)
        initial_ar = 0.0
        if 'account.move' in self.env:
            prior_invoices = self.env['account.move'].sudo().search([
                ('company_id', 'in', company_ids),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '<', f'{y1_start}-04-01')
            ])
            for inv in prior_invoices:
                if 'project.contract.management' in self.env and not is_linked_to_contract(inv):
                    continue
                residual = inv.currency_id._convert(
                    inv.amount_residual, target_currency,
                    get_rate_company(inv), inv.invoice_date or fields.Date.today()
                )
                if residual > 0:
                    initial_ar += residual

        # Cumulative DSO Amount across quarters/years
        cumulative_dso_amount = initial_ar

        # DSO running totals per year based on Billed and Actuals
        running_billed = {'y1': 0.0, 'y2': 0.0}
        running_actual = {'y1': 0.0, 'y2': 0.0}
        year_start_dates = {
            'y1': fields.Date.from_string(f'{y1_start}-04-01'),
            'y2': fields.Date.from_string(f'{y2_start}-04-01'),
        }

        for qdef in quarters_def:
            year_key = qdef['year']
            q_key = qdef['q']

            # 1. Bookings (Based on contract quarter breakdown if present, fallback to start date)
            booking_val = 0.0
            if 'project.contract.management' in self.env:
                contracts = self.env['project.contract.management'].sudo().search([
                    ('company_id', 'in', company_ids)
                ])
                q_start_dt = fields.Date.from_string(qdef['start'])
                q_end_dt = fields.Date.from_string(qdef['end'])
                for contract in contracts:
                    if contract.contract_start_date and q_start_dt <= contract.contract_start_date <= q_end_dt:
                        booking_val += contract.currency_id._convert(
                            contract.contract_amount, target_currency, get_rate_company(contract), contract.contract_start_date or fields.Date.today()
                        )

            # 2. Billed = invoiced amount (amount_total on posted customer invoices)
            # Actual = amount actually received for those invoices (amount_total - amount_residual)
            billed_val = 0.0
            actual_val = 0.0
            outstanding_val = 0.0  # AR still outstanding (amount_residual)
            invoices = self.env['account.move'].sudo().search([
                ('company_id', 'in', company_ids),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', qdef['start']),
                ('invoice_date', '<=', qdef['end'])
            ])
            for inv in invoices:
                if 'project.contract.management' in self.env and not is_linked_to_contract(inv):
                    continue
                inv_amount = inv.currency_id._convert(
                    inv.amount_total, target_currency,
                    get_rate_company(inv), inv.invoice_date or fields.Date.today()
                )
                # Billed = invoiced amount for contract-linked invoices
                billed_val += inv_amount
                # Actual = amount received = amount_total - amount_residual
                residual = inv.currency_id._convert(
                    inv.amount_residual, target_currency,
                    get_rate_company(inv), inv.invoice_date or fields.Date.today()
                )
                received = inv_amount - residual
                if received > 0:
                    actual_val += received
                # Outstanding AR = residual still to be collected
                if residual > 0:
                    outstanding_val += residual

            # 4. DSO Calculation based directly on Billed and Actuals
            # ------------------------------------------------------------------
            # DSO Amount = Cumulative Billed - Cumulative Actual (Carried forward across years)
            # DSO Days   = (DSO Amount / Cumulative Billed) × Days elapsed
            # ------------------------------------------------------------------
            q_start_date = fields.Date.from_string(qdef['start'])
            q_end_date   = fields.Date.from_string(qdef['end'])

            dso_amount_val = 0.0
            dso_days_val   = 0

            if q_start_date <= today_date:
                running_billed[year_key] += billed_val
                running_actual[year_key] += actual_val

                net_uncollected_q = billed_val - actual_val
                cumulative_dso_amount += net_uncollected_q
                cumulative_dso_amount = max(0.0, cumulative_dso_amount)

                dso_amount_val = cumulative_dso_amount

                # Days elapsed from year start to end of this quarter (or today if quarter not yet complete)
                year_start_dt = year_start_dates[year_key]
                effective_end = min(q_end_date, today_date)
                days_elapsed  = (effective_end - year_start_dt).days + 1

                if running_billed[year_key] > 0:
                    dso_days_val = round(
                        (cumulative_dso_amount / running_billed[year_key]) * days_elapsed
                    )
                else:
                    dso_days_val = 0

                if dso_days_val < 0:
                    dso_days_val = 0




            # 5. Expenses (Combination of hr.expense + vendor bills + payroll salary)
            expenses_val = 0.0

            # A. Expenses
            if 'hr.expense' in self.env:
                expenses = self.env['hr.expense'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('date', '>=', qdef['start']),
                    ('date', '<=', qdef['end'])
                ])
                for exp in expenses:
                    expenses_val += exp.currency_id._convert(
                        exp.total_amount_currency, target_currency, get_rate_company(exp), exp.date or fields.Date.today()
                    )

            # B. Vendor Bills
            if 'account.move' in self.env:
                bills = self.env['account.move'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('move_type', 'in', ('in_invoice', 'in_receipt', 'in_refund')),
                    ('expense_ids', '=', False),
                    ('invoice_date', '>=', qdef['start']),
                    ('invoice_date', '<=', qdef['end'])
                ])
                for bill in bills:
                    sign = -1.0 if bill.move_type == 'in_refund' else 1.0
                    expenses_val += sign * bill.currency_id._convert(
                        bill.amount_total, target_currency, get_rate_company(bill), bill.invoice_date or fields.Date.today()
                    )

            # C. Payroll / Payslips (Salary)
            if 'hr.payslip' in self.env:
                payslips = self.env['hr.payslip'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('date_to', '>=', qdef['start']),
                    ('date_to', '<=', qdef['end'])
                ])
                for slip in payslips:
                    net_amt = 0.0
                    if hasattr(slip, 'get_salary_line_total'):
                        net_amt = slip.get_salary_line_total('NET')
                    else:
                        line = slip.line_ids.filtered(lambda l: l.code == 'NET')
                        if line:
                            net_amt = line[0].total
                    
                    expenses_val += slip.company_id.currency_id._convert(
                        net_amt, target_currency, get_rate_company(slip), slip.date_to or fields.Date.today()
                    )





            # 6. Profit
            profit_val = billed_val - expenses_val

            # 7. Margin %
            margin_val = (profit_val / billed_val * 100) if billed_val > 0 else 0.0
            margin_val = min(100.0, margin_val)

            # 8. Cash Flow: Current cumulative Bank & Cash balance as of quarter end (effective_end)
            cash_flow_val = 0.0
            q_start_date = fields.Date.from_string(qdef['start'])
            q_end_date = fields.Date.from_string(qdef['end'])

            if q_start_date <= today_date:
                effective_end = q_end_date if q_end_date <= today_date else today_date
                if 'account.move.line' in self.env:
                    domain = [
                        ('company_id', 'in', company_ids),
                        ('parent_state', '=', 'posted'),
                        ('date', '<=', effective_end),
                        ('account_id.account_type', '=', 'asset_cash'),
                    ]
                    cash_lines = self.env['account.move.line'].sudo().search(domain)
                    bank_balance = 0.0
                    for cl in cash_lines:
                        line_amt = cl.debit - cl.credit
                        bank_balance += cl.company_id.currency_id._convert(
                            line_amt, target_currency, get_rate_company(cl), cl.date or fields.Date.today()
                        )
                    cash_flow_val = bank_balance

            # 9. Investors: Net cash flow (IN - OUT) from posted journal entries of partners with is_partner_investor=True + Cash Journal Entries (Unsecured Loan)
            calibration_val = 0.0
            if 'account.move.line' in self.env and q_start_date <= today_date:
                effective_end = q_end_date if q_end_date <= today_date else today_date
                cal_lines = self.env['account.move.line'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('move_id.move_type', '=', 'entry'),
                    ('parent_state', '=', 'posted'),
                    ('date', '>=', qdef['start']),
                    ('date', '<=', effective_end),
                    ('account_id.account_type', '!=', 'asset_cash'),
                    '|',
                    ('partner_id.is_partner_investor', '=', True),
                    ('journal_id.type', '=', 'cash')
                ])
                q_inv_in = 0.0
                q_inv_out = 0.0
                for line in cal_lines:
                    line_conv = line.company_id.currency_id._convert(
                        abs(line.debit - line.credit), target_currency, get_rate_company(line), line.date or fields.Date.today()
                    )
                    if line.credit > 0:
                        q_inv_in += line_conv
                    elif line.debit > 0:
                        q_inv_out += line_conv
                calibration_val = q_inv_in - q_inv_out

            if q_start_date > today_date:
                cash_flow_val = 0.0
                calibration_val = 0.0

            data[year_key][q_key] = {
                'booking': target_currency.round(booking_val),
                'billed': target_currency.round(billed_val),
                'actual': target_currency.round(actual_val),
                'dso_days': int(round(dso_days_val)),
                'dso_amount': target_currency.round(dso_amount_val),
                'expenses': target_currency.round(expenses_val),
                'profit': target_currency.round(profit_val),
                'margin': round(margin_val, 2),
                'cash_flow': target_currency.round(cash_flow_val),
                'calibration': target_currency.round(calibration_val)
            }

        # Calculate Totals for Year 1 and Year 2
        for y in ['y1', 'y2']:
            sum_booking = sum(data[y][q]['booking'] for q in ['q1', 'q2', 'q3', 'q4'])
            sum_billed = sum(data[y][q]['billed'] for q in ['q1', 'q2', 'q3', 'q4'])
            sum_actual = sum(data[y][q]['actual'] for q in ['q1', 'q2', 'q3', 'q4'])

            # DSO Amount & Days for Year Total based on Total Billed and Total Actual
            total_uncollected = max(0.0, sum_billed - sum_actual)
            sum_dso_amount = total_uncollected

            y_start_dt = year_start_dates[y]
            y_end_dt = fields.Date.from_string(f"{y1_start+1 if y == 'y1' else y2_start+1:04d}-03-31")
            effective_year_end = min(y_end_dt, today_date)
            year_days_elapsed = (effective_year_end - y_start_dt).days + 1

            if sum_billed > 0:
                avg_dso_days = round((total_uncollected / sum_billed) * year_days_elapsed)
            else:
                avg_dso_days = 0
            sum_expenses = sum(data[y][q]['expenses'] for q in ['q1', 'q2', 'q3', 'q4'])
            total_profit = sum_billed - sum_expenses
            total_margin = (total_profit / sum_billed * 100) if sum_billed > 0 else 0.0
            total_margin = min(100.0, total_margin)

            active_q = 'q4'
            y_start = y1_start if y == 'y1' else y2_start
            if y_start == current_fy_start:
                if today_date.month in [4, 5, 6]:
                    active_q = 'q1'
                elif today_date.month in [7, 8, 9]:
                    active_q = 'q2'
                elif today_date.month in [10, 11, 12]:
                    active_q = 'q3'
                else:
                    active_q = 'q4'

            sum_cash_flow = data[y][active_q]['cash_flow']
            sum_calibration = sum(data[y][q]['calibration'] for q in ['q1', 'q2', 'q3', 'q4'])

            data[y]['total'] = {
                'booking': target_currency.round(sum_booking),
                'billed': target_currency.round(sum_billed),
                'actual': target_currency.round(sum_actual),
                'dso_days': int(round(avg_dso_days)),
                'dso_amount': target_currency.round(sum_dso_amount),
                'expenses': target_currency.round(sum_expenses),
                'profit': target_currency.round(total_profit),
                'margin': round(total_margin, 2),
                'cash_flow': target_currency.round(sum_cash_flow),
                'calibration': target_currency.round(sum_calibration)
            }

        # Calculate Detailed Contracts Data (Revenue section)
        contracts_data = []
        from datetime import date as _date_rev
        total_contract_value = 0.0
        total_y1_booking = 0.0
        total_y1_billed = 0.0
        total_y2_booking = 0.0
        total_y2_billed = 0.0

        if 'project.contract.management' in self.env:
            all_contracts = self.env['project.contract.management'].sudo().search([
                ('company_id', 'in', company_ids)
            ])
            
            partners_data = {}
            
            for contract in all_contracts:
                # Engagement
                engagement = ''
                if contract.contract_type:
                    engagement_dict = dict(self.env['project.contract.management']._fields['contract_type'].selection or [])
                    engagement = engagement_dict.get(contract.contract_type, '')

                # Year 1 Dates
                y1_start_date = _date_rev(y1_start, 4, 1)
                y1_end_date = _date_rev(y1_start + 1, 3, 31)

                # Year 2 Dates
                y2_start_date = _date_rev(y2_start, 4, 1)
                y2_end_date = _date_rev(y2_start + 1, 3, 31)

                y1_booking = 0.0
                y2_booking = 0.0

                if contract.contract_start_date:
                    val_converted = contract.currency_id._convert(
                        contract.contract_amount, target_currency, get_rate_company(contract), contract.contract_start_date or fields.Date.today()
                    )
                    if y1_start_date <= contract.contract_start_date <= y1_end_date:
                        y1_booking += val_converted
                    elif y2_start_date <= contract.contract_start_date <= y2_end_date:
                        y2_booking += val_converted

                # Billed Y1 & Y2 and Actual Y1 & Y2
                y1_billed = 0.0
                y2_billed = 0.0
                y1_actual = 0.0
                y2_actual = 0.0

                # Search invoices linked to this contract (use sudo to bypass company record rules)
                invoices = self.env['account.move'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted')
                ])

                for inv in invoices:
                    is_linked = False
                    if inv.contract_id and inv.contract_id.id == contract.id:
                        is_linked = True
                    elif inv.id in contract.invoice_ids.ids:
                        is_linked = True
                    else:
                        sale_orders = inv.line_ids.sale_line_ids.order_id
                        if sale_orders:
                            linked_contracts = self.env['project.contract.management'].sudo().search([
                                ('sale_order_ids', 'in', sale_orders.ids),
                                ('company_id', 'in', company_ids)
                            ])
                            if contract.id in linked_contracts.ids:
                                is_linked = True

                    if is_linked:
                        inv_date = inv.invoice_date
                        if inv_date:
                            inv_val = inv.currency_id._convert(
                                inv.amount_total, target_currency, get_rate_company(inv), inv_date
                            )
                            # Actual = amount already received (amount_total - amount_residual)
                            residual_val = inv.currency_id._convert(
                                inv.amount_residual, target_currency, get_rate_company(inv), inv_date
                            )
                            received_val = max(0.0, inv_val - residual_val)

                            if y1_start_date <= inv_date <= y1_end_date:
                                y1_billed += inv_val
                                y1_actual += received_val
                            elif y2_start_date <= inv_date <= y2_end_date:
                                y2_billed += inv_val
                                y2_actual += received_val

                # Convert contract amount to target currency
                val_converted = contract.currency_id._convert(
                    contract.contract_amount, target_currency, get_rate_company(contract), fields.Date.today()
                )

                clients = contract.client_ids or [self.env['res.partner']]
                for client in clients:
                    partner_name = client.name or 'Unknown Customer'
                    partner_key = partner_name.strip().lower()
                    if partner_key not in partners_data:
                        partners_data[partner_key] = {
                            'customer': partner_name,
                            'industry': client.industry_id.name or contract.industry_id.name or '',
                            'businesses': set(),
                            'engagements': set(),
                            'contract_value': 0.0,
                            'y1_booking': 0.0,
                            'y1_billed': 0.0,
                            'y1_actual': 0.0,
                            'y2_booking': 0.0,
                            'y2_billed': 0.0,
                            'y2_actual': 0.0,
                        }
                    pd = partners_data[partner_key]
                    service_line_name = contract.service_line_id.name if contract.service_line_id else ''
                    if service_line_name:
                        pd['businesses'].add(service_line_name)
                    if engagement:
                        pd['engagements'].add(engagement)
                    pd['contract_value'] += val_converted
                    pd['y1_booking'] += y1_booking
                    pd['y1_billed'] += y1_billed
                    pd['y1_actual'] += y1_actual
                    pd['y2_booking'] += y2_booking
                    pd['y2_billed'] += y2_billed
                    pd['y2_actual'] += y2_actual

            for key, pd in partners_data.items():
                contracts_data.append({
                    'industry': pd['industry'],
                    'customers': pd['customer'],
                    'business': ', '.join(sorted(pd['businesses'])) or '',
                    'engagement': ', '.join(sorted(pd['engagements'])) or '',
                    'contract_value': target_currency.round(pd['contract_value']),
                    'y1_booking': target_currency.round(pd['y1_booking']),
                    'y1_billed': target_currency.round(pd['y1_billed']),
                    'y1_actual': target_currency.round(pd['y1_actual']),
                    'y1_expenses': 0.0,
                    'y1_margin': 0.0,
                    'y2_booking': target_currency.round(pd['y2_booking']),
                    'y2_billed': target_currency.round(pd['y2_billed']),
                    'y2_actual': target_currency.round(pd['y2_actual']),
                    'y2_expenses': 0.0,
                    'y2_margin': 0.0
                })

        total_contract_value = sum(c['contract_value'] for c in contracts_data)
        total_y1_booking = sum(c['y1_booking'] for c in contracts_data)
        total_y1_billed = sum(c['y1_billed'] for c in contracts_data)
        total_y1_actual = sum(c['y1_actual'] for c in contracts_data)
        total_y2_booking = sum(c['y2_booking'] for c in contracts_data)
        total_y2_billed = sum(c['y2_billed'] for c in contracts_data)
        total_y2_actual = sum(c['y2_actual'] for c in contracts_data)

        # Calculate Detailed Expense Data consolidated by Category
        expenses_data = []
        from datetime import date as _date

        categories_dict = {}

        def _add_expense_val(cat_label, y_key, val_booked, val_billed):
            if cat_label not in categories_dict:
                categories_dict[cat_label] = {
                    'category': cat_label,
                    'y1_booked': 0.0,
                    'y1_billed': 0.0,
                    'y2_booked': 0.0,
                    'y2_billed': 0.0,
                }
            categories_dict[cat_label][f'{y_key}_booked'] += val_booked
            categories_dict[cat_label][f'{y_key}_billed'] += val_billed

        y1_start_date = _date(y1_start, 4, 1)
        y1_end_date = _date(y1_start + 1, 3, 31)
        y2_start_date = _date(y2_start, 4, 1)
        y2_end_date = _date(y2_start + 1, 3, 31)

        def _get_y_key(rec_date):
            if rec_date and y1_start_date <= rec_date <= y1_end_date:
                return 'y1'
            elif rec_date and y2_start_date <= rec_date <= y2_end_date:
                return 'y2'
            return None

        # A. hr.expense -> consolidated under "Employee(reimbursement)"
        if 'hr.expense' in self.env:
            exps = self.env['hr.expense'].sudo().search([
                ('company_id', 'in', company_ids),
                ('date', '>=', y1_start_date),
                ('date', '<=', y2_end_date),
            ])
            for exp in exps:
                y_key = _get_y_key(exp.date)
                if not y_key:
                    continue
                conv = exp.currency_id._convert(
                    exp.total_amount_currency, target_currency,
                    get_rate_company(exp), exp.date or fields.Date.today()
                )
                is_paid = getattr(exp, 'state', '') in ('paid', 'posted', 'in_payment', 'done')
                actual_exp = conv if is_paid else 0.0
                _add_expense_val('Employee(reimbursement)', y_key, conv, actual_exp)

        # B. Vendor Bills -> consolidated by vendor_category
        category_labels = {
            'technology': 'Technology',
            'miscellaneous': 'Miscellaneous',
            'employee': 'Employee',
            'travel': 'Travel',
            'administration': 'Administration',
        }
        if 'account.move' in self.env:
            bills = self.env['account.move'].sudo().search([
                ('company_id', 'in', company_ids),
                ('move_type', 'in', ('in_invoice', 'in_receipt', 'in_refund')),
                ('expense_ids', '=', False),
                ('invoice_date', '>=', y1_start_date),
                ('invoice_date', '<=', y2_end_date),
            ])
            for bill in bills:
                y_key = _get_y_key(bill.invoice_date)
                if not y_key:
                    continue
                partner = bill.partner_id
                vendor_cat = partner.vendor_category if partner else 'miscellaneous'
                if not vendor_cat:
                    vendor_cat = 'miscellaneous'
                cat_label = category_labels.get(vendor_cat, 'Miscellaneous')

                sign = -1.0 if bill.move_type == 'in_refund' else 1.0
                conv = sign * bill.currency_id._convert(
                    bill.amount_total, target_currency,
                    get_rate_company(bill), bill.invoice_date or fields.Date.today()
                )
                residual = sign * bill.currency_id._convert(
                    bill.amount_residual, target_currency,
                    get_rate_company(bill), bill.invoice_date or fields.Date.today()
                )
                paid_amt = max(0.0, conv - residual)
                _add_expense_val(cat_label, y_key, conv, paid_amt)

        # C. Payroll / Payslips -> consolidated under "Employee(salary)"
        if 'hr.payslip' in self.env:
            payslips = self.env['hr.payslip'].sudo().search([
                ('company_id', 'in', company_ids),
                ('date_to', '>=', y1_start_date),
                ('date_to', '<=', y2_end_date),
            ])
            y1_salaries = []
            y2_salaries = []
            for slip in payslips:
                y_key = _get_y_key(slip.date_to)
                if not y_key:
                    continue
                net_amt = 0.0
                if hasattr(slip, 'get_salary_line_total'):
                    net_amt = slip.get_salary_line_total('NET')
                else:
                    line = slip.line_ids.filtered(lambda l: l.code == 'NET')
                    if line:
                        net_amt = line[0].total
                conv = slip.company_id.currency_id._convert(
                    net_amt, target_currency, get_rate_company(slip), slip.date_to or fields.Date.today()
                )
                if y_key == 'y1':
                    y1_salaries.append((slip.date_to, conv))
                elif y_key == 'y2':
                    y2_salaries.append((slip.date_to, conv))

            today = fields.Date.today()
            current_ym = today.strftime('%Y-%m')

            def _calc_year_salary(salaries, start_date, end_date):
                actual_val = sum(val for date_val, val in salaries)
                if end_date < today:
                    return actual_val, actual_val

                # Ongoing financial year:
                # Exclude the current ongoing month from the average calculation
                past_salaries = [val for d, val in salaries if d and d.strftime('%Y-%m') < current_ym]
                total_past_sal = sum(past_salaries)
                elapsed_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
                plan_val = (total_past_sal / elapsed_months * 12) if elapsed_months > 0 else actual_val
                return plan_val, actual_val

            y1_plan, y1_actual = _calc_year_salary(y1_salaries, y1_start_date, y1_end_date)
            y2_plan, y2_actual = _calc_year_salary(y2_salaries, y2_start_date, y2_end_date)

            _add_expense_val('Employee(salary)', 'y1', y1_plan, y1_actual)
            _add_expense_val('Employee(salary)', 'y2', y2_plan, y2_actual)

        # Populate expenses_data
        for cat_label in sorted(categories_dict.keys()):
            r = categories_dict[cat_label]
            expenses_data.append({
                'category': r['category'],
                'y1_booked': target_currency.round(r['y1_booked']),
                'y1_billed': target_currency.round(r['y1_billed']),
                'y2_booked': target_currency.round(r['y2_booked']),
                'y2_billed': target_currency.round(r['y2_billed']),
            })

        salary_data = []
        total_exp_y1_booked = target_currency.round(sum(e['y1_booked'] for e in expenses_data))
        total_exp_y1_billed = target_currency.round(sum(e['y1_billed'] for e in expenses_data))
        total_exp_y2_booked = target_currency.round(sum(e['y2_booked'] for e in expenses_data))
        total_exp_y2_billed = target_currency.round(sum(e['y2_billed'] for e in expenses_data))

        total_sal_y1_booked = 0.0
        total_sal_y2_booked = 0.0

        # Monthly Cash Flow Section Calculation (Month-Wise Format)
        import calendar
        months_def = [
            {'name': 'April', 'm': 4, 'year_offset': 0},
            {'name': 'May', 'm': 5, 'year_offset': 0},
            {'name': 'June', 'm': 6, 'year_offset': 0},
            {'name': 'July', 'm': 7, 'year_offset': 0},
            {'name': 'August', 'm': 8, 'year_offset': 0},
            {'name': 'September', 'm': 9, 'year_offset': 0},
            {'name': 'October', 'm': 10, 'year_offset': 0},
            {'name': 'November', 'm': 11, 'year_offset': 0},
            {'name': 'December', 'm': 12, 'year_offset': 0},
            {'name': 'January', 'm': 1, 'year_offset': 1},
            {'name': 'February', 'm': 2, 'year_offset': 1},
            {'name': 'March', 'm': 3, 'year_offset': 1},
        ]

        # Monthly Cash Flow: Strictly use only lines where the account itself is a bank/cash account (asset_cash)
        # This avoids double-counting counterpart lines (receivables, payables) that appear in the same journal entry
        # IN  = all debits on bank/cash accounts (customer payments, fund receipts, any money in)
        # OUT = all credits on bank/cash accounts (vendor payments, expenses paid, salary paid)
        # Remaining = IN - OUT
        monthly_cashflow = []

        def _get_bank_cash_account_type_domain(env, company_ids, date_gte, date_lte):
            """Domain that strictly targets the bank/cash account line only."""
            return [
                ('company_id', 'in', company_ids),
                ('parent_state', '=', 'posted'),
                ('date', '>=', date_gte),
                ('date', '<=', date_lte),
                ('account_id.account_type', '=', 'asset_cash'),
            ]

        for mdef in months_def:
            row_data = {
                'month': mdef['name'],
                'y1_in': 0.0,
                'y1_out': 0.0,
                'y1_remaining': 0.0,
                'y2_in': 0.0,
                'y2_out': 0.0,
                'y2_remaining': 0.0,
            }

            for y_key, start_yr in [('y1', y1_start), ('y2', y2_start)]:
                cal_yr = start_yr + mdef['year_offset']
                m_num = mdef['m']
                last_day = calendar.monthrange(cal_yr, m_num)[1]
                m_start_str = f"{cal_yr:04d}-{m_num:02d}-01"
                m_end_str = f"{cal_yr:04d}-{m_num:02d}-{last_day:02d}"
                m_start_dt = fields.Date.from_string(m_start_str)

                in_val = 0.0
                out_val = 0.0

                if m_start_dt <= today_date:
                    st_lines = False
                    if 'account.bank.statement.line' in self.env:
                        bs_domain = [
                            ('company_id', 'in', company_ids),
                            ('date', '>=', m_start_str),
                            ('date', '<=', m_end_str),
                        ]
                        st_lines = self.env['account.bank.statement.line'].sudo().search(bs_domain)

                    if st_lines:
                        for stl in st_lines:
                            amt = stl.amount
                            curr = getattr(stl, 'foreign_currency_id', False) or stl.currency_id or stl.company_id.currency_id
                            converted = curr._convert(
                                abs(amt), target_currency, get_rate_company(stl), stl.date or fields.Date.today()
                            )
                            if amt > 0:
                                in_val += converted
                            elif amt < 0:
                                out_val += converted
                    elif 'account.move.line' in self.env:
                        domain_month = _get_bank_cash_account_type_domain(
                            self.env, company_ids, m_start_str, m_end_str
                        )
                        m_lines = self.env['account.move.line'].sudo().search(domain_month)
                        for ml in m_lines:
                            if ml.debit > 0:
                                in_val += ml.company_id.currency_id._convert(
                                    ml.debit, target_currency, get_rate_company(ml), ml.date or fields.Date.today()
                                )
                            elif ml.credit > 0:
                                out_val += ml.company_id.currency_id._convert(
                                    ml.credit, target_currency, get_rate_company(ml), ml.date or fields.Date.today()
                                )

                row_data[f'{y_key}_in'] = target_currency.round(in_val)
                row_data[f'{y_key}_out'] = target_currency.round(out_val)
                row_data[f'{y_key}_remaining'] = target_currency.round(in_val - out_val)

            monthly_cashflow.append(row_data)

        total_cf_y1_in = target_currency.round(sum(m['y1_in'] for m in monthly_cashflow))
        total_cf_y1_out = target_currency.round(sum(m['y1_out'] for m in monthly_cashflow))
        total_cf_y1_remaining = target_currency.round(total_cf_y1_in - total_cf_y1_out)

        total_cf_y2_in = target_currency.round(sum(m['y2_in'] for m in monthly_cashflow))
        total_cf_y2_out = target_currency.round(sum(m['y2_out'] for m in monthly_cashflow))
        total_cf_y2_remaining = target_currency.round(total_cf_y2_in - total_cf_y2_out)

        # Calibration / Investors Section Calculation (Only partners marked with is_partner_investor=True)
        def get_q_num(d_str, fy_yr):
            if f"{fy_yr:04d}-04-01" <= d_str <= f"{fy_yr:04d}-06-30":
                return 1
            elif f"{fy_yr:04d}-07-01" <= d_str <= f"{fy_yr:04d}-09-30":
                return 2
            elif f"{fy_yr:04d}-10-01" <= d_str <= f"{fy_yr:04d}-12-31":
                return 3
            elif f"{fy_yr+1:04d}-01-01" <= d_str <= f"{fy_yr+1:04d}-03-31":
                return 4
            return None

        y1_fy_start = y1_start
        y2_cy_start = y2_start
        y1_start_str = f"{y1_fy_start:04d}-04-01"
        y1_end_str = f"{y1_fy_start+1:04d}-03-31"
        y2_start_str = f"{y2_cy_start:04d}-04-01"
        y2_end_str = today_date.strftime('%Y-%m-%d') if today_date <= fields.Date.from_string(f"{y2_cy_start+1:04d}-03-31") else f"{y2_cy_start+1:04d}-03-31"

        investor_data_map = {}

        if 'account.move' in self.env and 'res.partner' in self.env:
            # Only partners marked with is_partner_investor as True
            investor_partners = self.env['res.partner'].sudo().search([
                ('is_partner_investor', '=', True)
            ])

            for partner in investor_partners:
                partner_name = partner.name.strip() if partner.name else 'Unknown Partner'
                category = ', '.join(partner.category_id.mapped('name')) if partner.category_id else 'General'
                partner_key = partner.id

                if partner_key not in investor_data_map:
                    investor_data_map[partner_key] = {
                        'name': partner_name,
                        'category': category,
                        'y1_q_in': {f'q{i}': 0.0 for i in range(1, 5)},
                        'y1_q_out': {f'q{i}': 0.0 for i in range(1, 5)},
                        'y2_q_in': {f'q{i}': 0.0 for i in range(1, 5)},
                        'y2_q_out': {f'q{i}': 0.0 for i in range(1, 5)},
                    }

                moves = self.env['account.move'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('move_type', '=', 'entry'),
                    ('state', '=', 'posted'),
                    ('date', '>=', min(y1_start_str, y2_start_str)),
                    ('date', '<=', max(y1_end_str, y2_end_str)),
                    '|', ('partner_id', '=', partner.id), ('line_ids.partner_id', '=', partner.id)
                ])

                for move in moves:
                    ldate = move.date
                    if not ldate:
                        continue
                    ldate_str = ldate.strftime('%Y-%m-%d')

                    for line in move.line_ids:
                        if (line.partner_id == partner or (not line.partner_id and move.partner_id == partner)) and line.account_id.account_type != 'asset_cash':
                            line_conv = line.company_id.currency_id._convert(
                                abs(line.debit - line.credit), target_currency, get_rate_company(line), line.date or fields.Date.today()
                            )
                            if line.credit > 0:
                                if y1_start_str <= ldate_str <= y1_end_str:
                                    q_num = get_q_num(ldate_str, y1_fy_start)
                                    if q_num:
                                        investor_data_map[partner_key]['y1_q_in'][f'q{q_num}'] += line_conv
                                if y2_start_str <= ldate_str <= y2_end_str:
                                    q_num = get_q_num(ldate_str, y2_cy_start)
                                    if q_num:
                                        investor_data_map[partner_key]['y2_q_in'][f'q{q_num}'] += line_conv
                            elif line.debit > 0:
                                if y1_start_str <= ldate_str <= y1_end_str:
                                    q_num = get_q_num(ldate_str, y1_fy_start)
                                    if q_num:
                                        investor_data_map[partner_key]['y1_q_out'][f'q{q_num}'] += line_conv
                                if y2_start_str <= ldate_str <= y2_end_str:
                                    q_num = get_q_num(ldate_str, y2_cy_start)
                                    if q_num:
                                        investor_data_map[partner_key]['y2_q_out'][f'q{q_num}'] += line_conv

            # Process Cash Journal Entries for "Unsecured Loan" row
            unsecured_loan_key = 'unsecured_loan'
            investor_data_map[unsecured_loan_key] = {
                'name': 'Unsecured Loan',
                'category': 'Unsecured Loan',
                'y1_q_in': {f'q{i}': 0.0 for i in range(1, 5)},
                'y1_q_out': {f'q{i}': 0.0 for i in range(1, 5)},
                'y2_q_in': {f'q{i}': 0.0 for i in range(1, 5)},
                'y2_q_out': {f'q{i}': 0.0 for i in range(1, 5)},
            }

            cash_moves = self.env['account.move'].sudo().search([
                ('company_id', 'in', company_ids),
                ('move_type', '=', 'entry'),
                ('journal_id.type', '=', 'cash'),
                ('state', '=', 'posted'),
                ('date', '>=', min(y1_start_str, y2_start_str)),
                ('date', '<=', max(y1_end_str, y2_end_str)),
            ])

            for move in cash_moves:
                ldate = move.date
                if not ldate:
                    continue
                ldate_str = ldate.strftime('%Y-%m-%d')

                for line in move.line_ids:
                    if line.account_id.account_type != 'asset_cash':
                        line_conv = line.company_id.currency_id._convert(
                            abs(line.debit - line.credit), target_currency, get_rate_company(line), line.date or fields.Date.today()
                        )
                        if line.credit > 0:
                            if y1_start_str <= ldate_str <= y1_end_str:
                                q_num = get_q_num(ldate_str, y1_fy_start)
                                if q_num:
                                    investor_data_map[unsecured_loan_key]['y1_q_in'][f'q{q_num}'] += line_conv
                            if y2_start_str <= ldate_str <= y2_end_str:
                                q_num = get_q_num(ldate_str, y2_cy_start)
                                if q_num:
                                    investor_data_map[unsecured_loan_key]['y2_q_in'][f'q{q_num}'] += line_conv
                        elif line.debit > 0:
                            if y1_start_str <= ldate_str <= y1_end_str:
                                q_num = get_q_num(ldate_str, y1_fy_start)
                                if q_num:
                                    investor_data_map[unsecured_loan_key]['y1_q_out'][f'q{q_num}'] += line_conv
                            if y2_start_str <= ldate_str <= y2_end_str:
                                q_num = get_q_num(ldate_str, y2_cy_start)
                                if q_num:
                                    investor_data_map[unsecured_loan_key]['y2_q_out'][f'q{q_num}'] += line_conv

        investor_rows = []
        for inv_key in sorted(investor_data_map.keys(), key=lambda k: investor_data_map[k]['name']):
            inv_info = investor_data_map[inv_key]

            y1_q1_in = inv_info['y1_q_in']['q1']
            y1_q1_out = inv_info['y1_q_out']['q1']
            y1_q2_in = inv_info['y1_q_in']['q2']
            y1_q2_out = inv_info['y1_q_out']['q2']
            y1_q3_in = inv_info['y1_q_in']['q3']
            y1_q3_out = inv_info['y1_q_out']['q3']
            y1_q4_in = inv_info['y1_q_in']['q4']
            y1_q4_out = inv_info['y1_q_out']['q4']

            y1_tot_in = y1_q1_in + y1_q2_in + y1_q3_in + y1_q4_in
            y1_tot_out = y1_q1_out + y1_q2_out + y1_q3_out + y1_q4_out

            y2_q1_in = inv_info['y2_q_in']['q1']
            y2_q1_out = inv_info['y2_q_out']['q1']
            y2_q2_in = inv_info['y2_q_in']['q2']
            y2_q2_out = inv_info['y2_q_out']['q2']
            y2_q3_in = inv_info['y2_q_in']['q3']
            y2_q3_out = inv_info['y2_q_out']['q3']
            y2_q4_in = inv_info['y2_q_in']['q4']
            y2_q4_out = inv_info['y2_q_out']['q4']

            y2_tot_in = y2_q1_in + y2_q2_in + y2_q3_in + y2_q4_in
            y2_tot_out = y2_q1_out + y2_q2_out + y2_q3_out + y2_q4_out

            if (y1_tot_in < 0.01 and y1_tot_out < 0.01 and y2_tot_in < 0.01 and y2_tot_out < 0.01):
                continue

            row = {
                'investor': inv_info['name'],
                'category': inv_info['category'],

                'y1_q1_in': target_currency.round(y1_q1_in),
                'y1_q1_out': target_currency.round(y1_q1_out),
                'y1_q2_in': target_currency.round(y1_q2_in),
                'y1_q2_out': target_currency.round(y1_q2_out),
                'y1_q3_in': target_currency.round(y1_q3_in),
                'y1_q3_out': target_currency.round(y1_q3_out),
                'y1_q4_in': target_currency.round(y1_q4_in),
                'y1_q4_out': target_currency.round(y1_q4_out),
                'y1_tot_in': target_currency.round(y1_tot_in),
                'y1_tot_out': target_currency.round(y1_tot_out),

                'y2_q1_in': target_currency.round(y2_q1_in),
                'y2_q1_out': target_currency.round(y2_q1_out),
                'y2_q2_in': target_currency.round(y2_q2_in),
                'y2_q2_out': target_currency.round(y2_q2_out),
                'y2_q3_in': target_currency.round(y2_q3_in),
                'y2_q3_out': target_currency.round(y2_q3_out),
                'y2_q4_in': target_currency.round(y2_q4_in),
                'y2_q4_out': target_currency.round(y2_q4_out),
                'y2_tot_in': target_currency.round(y2_tot_in),
                'y2_tot_out': target_currency.round(y2_tot_out),
            }
            investor_rows.append(row)

        investor_totals = {
            'y1_q1_in': target_currency.round(sum(r['y1_q1_in'] for r in investor_rows)),
            'y1_q1_out': target_currency.round(sum(r['y1_q1_out'] for r in investor_rows)),
            'y1_q2_in': target_currency.round(sum(r['y1_q2_in'] for r in investor_rows)),
            'y1_q2_out': target_currency.round(sum(r['y1_q2_out'] for r in investor_rows)),
            'y1_q3_in': target_currency.round(sum(r['y1_q3_in'] for r in investor_rows)),
            'y1_q3_out': target_currency.round(sum(r['y1_q3_out'] for r in investor_rows)),
            'y1_q4_in': target_currency.round(sum(r['y1_q4_in'] for r in investor_rows)),
            'y1_q4_out': target_currency.round(sum(r['y1_q4_out'] for r in investor_rows)),
            'y1_tot_in': target_currency.round(sum(r['y1_tot_in'] for r in investor_rows)),
            'y1_tot_out': target_currency.round(sum(r['y1_tot_out'] for r in investor_rows)),

            'y2_q1_in': target_currency.round(sum(r['y2_q1_in'] for r in investor_rows)),
            'y2_q1_out': target_currency.round(sum(r['y2_q1_out'] for r in investor_rows)),
            'y2_q2_in': target_currency.round(sum(r['y2_q2_in'] for r in investor_rows)),
            'y2_q2_out': target_currency.round(sum(r['y2_q2_out'] for r in investor_rows)),
            'y2_q3_in': target_currency.round(sum(r['y2_q3_in'] for r in investor_rows)),
            'y2_q3_out': target_currency.round(sum(r['y2_q3_out'] for r in investor_rows)),
            'y2_q4_in': target_currency.round(sum(r['y2_q4_in'] for r in investor_rows)),
            'y2_q4_out': target_currency.round(sum(r['y2_q4_out'] for r in investor_rows)),
            'y2_tot_in': target_currency.round(sum(r['y2_tot_in'] for r in investor_rows)),
            'y2_tot_out': target_currency.round(sum(r['y2_tot_out'] for r in investor_rows)),
        }

        y1_prefix = 'CY' if y1_start == current_fy_start else 'FY'
        y2_prefix = 'CY' if y2_start == current_fy_start else 'FY'

        return {
            'company_name': display_company_name,
            'company_name_only': company_name_only,
            'country_code': country_code_str,
            'currency_symbol': f"{target_currency.symbol} {target_currency.name}" if target_currency.symbol else target_currency.name,
            'year1_label': f'{y1_prefix}{y1_start - 2000 + 1} - {y1_start} -{y1_start + 1}',
            'year2_label': f'{y2_prefix}{y2_start - 2000 + 1} - {y2_start} -{y2_start + 1}',
            'y1_prefix': y1_prefix,
            'y2_prefix': y2_prefix,
            'y1_date_range_label': f'1st Apr-{y1_start-2000} to 31st Mar-{y1_start-2000+1}',
            'y1_short_label': f'{y1_prefix}{y1_start - 2000 + 1}',
            'y2_date_range_label': f'1st Apr-{y2_start-2000} to 31st Mar-{y2_start-2000+1}',
            'y2_short_label': f'{y2_prefix}{y2_start - 2000 + 1}',
            'data': data,
            'contracts_data': contracts_data,
            'total_contract_value': target_currency.round(total_contract_value),
            'total_y1_booking': target_currency.round(total_y1_booking),
            'total_y1_billed': target_currency.round(total_y1_billed),
            'total_y1_actual': target_currency.round(total_y1_actual),
            'total_y2_booking': target_currency.round(total_y2_booking),
            'total_y2_billed': target_currency.round(total_y2_billed),
            'total_y2_actual': target_currency.round(total_y2_actual),
            'total_y1_expenses': 0.0,
            'total_y1_margin': 0.0,
            'total_y2_expenses': 0.0,
            'total_y2_margin': 0.0,
            'expenses_data': expenses_data,
            'salary_data': salary_data,
            'total_exp_y1_booked': total_exp_y1_booked,
            'total_exp_y1_billed': total_exp_y1_billed,
            'total_exp_y2_booked': total_exp_y2_booked,
            'total_exp_y2_billed': total_exp_y2_billed,
            'total_sal_y1_booked': total_sal_y1_booked,
            'total_sal_y2_booked': total_sal_y2_booked,
            'monthly_cashflow': monthly_cashflow,
            'total_cf_y1_in': total_cf_y1_in,
            'total_cf_y1_out': total_cf_y1_out,
            'total_cf_y1_remaining': total_cf_y1_remaining,
            'total_cf_y2_in': total_cf_y2_in,
            'total_cf_y2_out': total_cf_y2_out,
            'total_cf_y2_remaining': total_cf_y2_remaining,
            'investor_rows': investor_rows,
            'investor_totals': investor_totals,
        }

