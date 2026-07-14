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
        return {
            'type': 'ir.actions.client',
            'tag': 'bxi_fbook_report_dashboard',
            'name': 'Fbook Report',
            'context': {
                'company_ids': self.company_ids.ids,
                'company_names': ", ".join(self.company_ids.mapped('name')),
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
        # Primary company used as fallback for currency rate lookups
        company = companies[0] if companies else self.env.company
        target_currency = self.env['res.currency'].browse(currency_id)

        def get_rate_company(record):
            """Return the record's own company for exchange rate lookup, or fallback."""
            rec_company = getattr(record, 'company_id', False)
            return rec_company if rec_company else company


        y2_start = int(start_financial_year)
        y1_start = y2_start - 1


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

        for qdef in quarters_def:
            year_key = qdef['year']
            q_key = qdef['q']

            # 1. Bookings (Based on contract quarter breakdown if present, fallback to start date) - COMMENTED OUT FOR NOW
            booking_val = 0.0
            # if 'project.contract.management' in self.env:
            #     contracts = self.env['project.contract.management'].search([
            #         ('company_id', 'in', company_ids)
            #     ])
            #     q_start_dt = fields.Date.from_string(qdef['start'])
            #     q_end_dt = fields.Date.from_string(qdef['end'])
            #     for contract in contracts:
            #
            #         if contract.contract_quarter_ids:
            #             q_lines = contract.contract_quarter_ids.filtered(
            #                 lambda l: l.invoice_date and q_start_dt <= l.invoice_date <= q_end_dt
            #             )
            #             for line in q_lines:
            #                 booking_val += contract.currency_id._convert(
            #                     line.amount, target_currency, get_rate_company(contract), fields.Date.today()
            #                 )
            #
            #         else:
            #             if contract.contract_start_date and q_start_dt <= contract.contract_start_date <= q_end_dt:
            #                 booking_val += contract.currency_id._convert(
            #                     contract.contract_amount, target_currency, get_rate_company(contract), fields.Date.today()
            #                 )




            # Helper function to check if an invoice is linked to a contract
            def is_linked_to_contract(inv):
                if inv.contract_id:
                    if not inv.contract_id.company_id or inv.contract_id.company_id.id in company_ids:
                        return True
                # Check via Many2many invoice_ids on contract model
                linked_m2m = self.env['project.contract.management'].search([
                    ('invoice_ids', 'in', [inv.id]),
                    '|', ('company_id', 'in', company_ids), ('company_id', '=', False)
                ])
                if linked_m2m:
                    return True
                # Check via Sales Orders
                sale_orders = inv.line_ids.sale_line_ids.order_id
                if sale_orders:
                    linked_contracts = self.env['project.contract.management'].search([
                        ('sale_order_ids', 'in', sale_orders.ids),
                        '|', ('company_id', 'in', company_ids), ('company_id', '=', False)
                    ])
                    if linked_contracts:
                        return True
                return False



            # 2. Billed — ALL posted customer invoices for selected companies in the quarter
            billed_val = 0.0
            actual_val = 0.0
            invoices = self.env['account.move'].search([
                ('company_id', 'in', company_ids),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', qdef['start']),
                ('invoice_date', '<=', qdef['end'])
            ])
            for inv in invoices:
                inv_amount = inv.currency_id._convert(
                    inv.amount_total, target_currency,
                    get_rate_company(inv), inv.invoice_date or fields.Date.today()
                )
                # Billed = ALL posted invoices raised in the quarter
                billed_val += inv_amount
                # Actual = invoices that are fully paid (payment_state = paid)
                if inv.payment_state == 'paid':

                    actual_val += inv_amount






            # 4. DSO — Split into DSO (Days) and DSO (Amount)
            dso_days_val = 0.0
            dso_amount_val = billed_val - actual_val




            # 5. Expenses (Combination of hr.expense + vendor bills + payroll salary)
            expenses_val = 0.0

            # A. Expenses
            if 'hr.expense' in self.env:
                expenses = self.env['hr.expense'].search([
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
                bills = self.env['account.move'].search([
                    ('company_id', 'in', company_ids),
                    ('move_type', '=', 'in_invoice'),
                    ('invoice_date', '>=', qdef['start']),
                    ('invoice_date', '<=', qdef['end'])
                ])
                for bill in bills:
                    expenses_val += bill.currency_id._convert(
                        bill.amount_total, target_currency, get_rate_company(bill), bill.invoice_date or fields.Date.today()
                    )

            # C. Payroll / Payslips (Salary)
            if 'hr.payslip' in self.env:
                payslips = self.env['hr.payslip'].search([
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

            data[year_key][q_key] = {
                'booking': target_currency.round(booking_val),
                'billed': target_currency.round(billed_val),
                'actual': target_currency.round(actual_val),
                'dso_days': round(dso_days_val, 2),
                'dso_amount': target_currency.round(dso_amount_val),
                'expenses': target_currency.round(expenses_val),
                'profit': target_currency.round(profit_val),
                'margin': round(margin_val, 2)
            }

        # Calculate Totals for Year 1 and Year 2
        for y in ['y1', 'y2']:
            sum_booking = sum(data[y][q]['booking'] for q in ['q1', 'q2', 'q3', 'q4'])
            sum_billed = sum(data[y][q]['billed'] for q in ['q1', 'q2', 'q3', 'q4'])
            sum_actual = sum(data[y][q]['actual'] for q in ['q1', 'q2', 'q3', 'q4'])
            avg_dso_days = sum(data[y][q]['dso_days'] for q in ['q1', 'q2', 'q3', 'q4']) / 4.0
            sum_dso_amount = sum(data[y][q]['dso_amount'] for q in ['q1', 'q2', 'q3', 'q4'])
            sum_expenses = sum(data[y][q]['expenses'] for q in ['q1', 'q2', 'q3', 'q4'])
            total_profit = sum_billed - sum_expenses
            total_margin = (total_profit / sum_billed * 100) if sum_billed > 0 else 0.0

            data[y]['total'] = {
                'booking': target_currency.round(sum_booking),
                'billed': target_currency.round(sum_billed),
                'actual': target_currency.round(sum_actual),
                'dso_days': round(avg_dso_days, 2),
                'dso_amount': target_currency.round(sum_dso_amount),
                'expenses': target_currency.round(sum_expenses),
                'profit': target_currency.round(total_profit),
                'margin': round(total_margin, 2)
            }

        # Calculate Detailed Contracts Data
        contracts_data = []
        from datetime import date
        total_contract_value = 0.0
        total_y1_booking = 0.0
        total_y1_billed = 0.0
        total_y2_booking = 0.0
        total_y2_billed = 0.0

        if 'project.contract.management' in self.env:
            all_contracts = self.env['project.contract.management'].search([
                ('company_id', 'in', company_ids)
            ])
            for contract in all_contracts:


                # Period
                start_str = contract.contract_start_date.strftime('%d-%b-%y') if contract.contract_start_date else ''
                end_str = contract.contract_end_date.strftime('%d-%b-%y') if contract.contract_end_date else ''
                period = f"{start_str} to {end_str}" if (start_str or end_str) else ''

                # Engagement
                engagement = ''
                if contract.contract_type:
                    engagement_dict = dict(self.env['project.contract.management']._fields['contract_type'].selection or [])
                    engagement = engagement_dict.get(contract.contract_type, '')

                # Year 1 Dates
                y1_start_date = date(y1_start, 4, 1)
                y1_end_date = date(y1_start + 1, 3, 31)

                # Year 2 Dates
                y2_start_date = date(y2_start, 4, 1)
                y2_end_date = date(y2_start + 1, 3, 31)

                # Booking Y1 & Y2 based on breakdown lines if present, fallback to start date - COMMENTED OUT FOR NOW
                y1_booking = 0.0
                y2_booking = 0.0
                # if contract.contract_quarter_ids:
                #     # Year 1 Lines
                #     y1_lines = contract.contract_quarter_ids.filtered(
                #         lambda l: l.invoice_date and y1_start_date <= l.invoice_date <= y1_end_date
                #     )
                #     for line in y1_lines:
                #         y1_booking += contract.currency_id._convert(
                #             line.amount, target_currency, get_rate_company(contract), fields.Date.today()
                #         )
                #
                #     # Year 2 Lines
                #     y2_lines = contract.contract_quarter_ids.filtered(
                #         lambda l: l.invoice_date and y2_start_date <= l.invoice_date <= y2_end_date
                #     )
                #     for line in y2_lines:
                #         y2_booking += contract.currency_id._convert(
                #             line.amount, target_currency, get_rate_company(contract), fields.Date.today()
                #         )
                #
                # else:
                #     if contract.contract_start_date:
                #         if y1_start_date <= contract.contract_start_date <= y1_end_date:
                #             y1_booking = contract.currency_id._convert(
                #                 contract.contract_amount, target_currency, get_rate_company(contract), fields.Date.today()
                #             )
                #         elif y2_start_date <= contract.contract_start_date <= y2_end_date:
                #             y2_booking = contract.currency_id._convert(
                #                 contract.contract_amount, target_currency, get_rate_company(contract), fields.Date.today()
                #             )



                # Billed Y1 & Y2
                y1_billed = 0.0
                y2_billed = 0.0

                # Billed Y1 & Y2: all customer invoices except cancel
                invoices = self.env['account.move'].search([
                    ('company_id', 'in', company_ids),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '!=', 'cancel'),
                    ('partner_id', 'in', contract.client_ids.ids)
                ])

                for inv in invoices:
                    inv_date = inv.invoice_date
                    if inv_date:
                        inv_val = inv.currency_id._convert(
                            inv.amount_total, target_currency, get_rate_company(inv), inv_date
                        )

                        if y1_start_date <= inv_date <= y1_end_date:
                            y1_billed += inv_val
                        elif y2_start_date <= inv_date <= y2_end_date:
                            y2_billed += inv_val

                # Convert contract amount to target currency
                val_converted = contract.currency_id._convert(
                    contract.contract_amount, target_currency, get_rate_company(contract), fields.Date.today()
                )


                contracts_data.append({
                    'industry': contract.industry_id.name or '',
                    'customers': ', '.join(contract.client_ids.mapped('name')) or '',
                    'business': contract.name,
                    'period': period,
                    'engagement': engagement,
                    'contract_value': target_currency.round(val_converted),
                    'y1_booking': target_currency.round(y1_booking),
                    'y1_billed': target_currency.round(y1_billed),
                    'y2_booking': target_currency.round(y2_booking),
                    'y2_billed': target_currency.round(y2_billed)
                })

        total_contract_value = sum(c['contract_value'] for c in contracts_data)
        total_y1_booking = sum(c['y1_booking'] for c in contracts_data)
        total_y1_billed = sum(c['y1_billed'] for c in contracts_data)
        total_y2_booking = sum(c['y2_booking'] for c in contracts_data)
        total_y2_billed = sum(c['y2_billed'] for c in contracts_data)

        return {
            'company_name': company.name,
            'currency_symbol': f"{target_currency.symbol} {target_currency.name}" if target_currency.symbol else target_currency.name,
            'year1_label': f'FY{y1_start - 2000 + 1} - {y1_start} -{y1_start + 1}',
            'year2_label': f'FY{y2_start - 2000 + 1} - {y2_start} -{y2_start + 1}',
            'y1_date_range_label': f'1st Apr-{y1_start-2000} to 31st Mar-{y1_start-2000+1}',
            'y1_short_label': f'FY{y1_start - 2000 + 1}',
            'y2_date_range_label': f'1st Apr-{y2_start-2000} to 31st Mar-{y2_start-2000+1}',
            'y2_short_label': f'FY{y2_start - 2000 + 1}',
            'data': data,
            'contracts_data': contracts_data,
            'total_contract_value': target_currency.round(total_contract_value),
            'total_y1_booking': target_currency.round(total_y1_booking),
            'total_y1_billed': target_currency.round(total_y1_billed),
            'total_y2_booking': target_currency.round(total_y2_booking),
            'total_y2_billed': target_currency.round(total_y2_billed),
        }

