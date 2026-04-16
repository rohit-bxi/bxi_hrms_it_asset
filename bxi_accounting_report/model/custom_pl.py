from collections import defaultdict
from odoo import models, api, fields


class CustomPLReport(models.Model):
    _name = 'custom.pl.report'

    @api.model
    def get_filtered_data(self, financial_year=None, quarters=None, company_ids=None):

        def get_quarter(date):
            if not date:
                return None
            m = date.month
            if m in [4, 5, 6]:
                return 'q1'
            elif m in [7, 8, 9]:
                return 'q2'
            elif m in [10, 11, 12]:
                return 'q3'
            else:
                return 'q4'

        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted')
        ])

        customers = defaultdict(lambda: {
            'salespersons': {},
            'total_booking': 0,
            'total_billing': 0,
            'quarters_projected': defaultdict(float),
            'quarters_actual': defaultdict(float),
            'country': '',
        })

        for inv in invoices:
            partner = inv.partner_id
            customer = partner.name or 'N/A'

            salesperson = inv.user_id.name or 'N/A'
            q = get_quarter(inv.invoice_date)

            cust = customers[customer]

            cust['country'] = partner.country_id.name or ''

            if salesperson not in cust['salespersons']:
                cust['salespersons'][salesperson] = {
                    'salesperson': salesperson,
                    'products': set(),
                    'booking': 0,
                    'billing': 0,
                    'quarters_projected': defaultdict(float),
                    'quarters_actual': defaultdict(float),
                }

            sp = cust['salespersons'][salesperson]

            products = inv.invoice_line_ids.mapped('product_id.name')
            sp['products'].update(products)

            company_currency = inv.company_id.currency_id
            target_currency = self.env.company.currency_id
            date = inv.invoice_date or fields.Date.today()
            projected = company_currency._convert(
                inv.amount_total,
                target_currency,
                inv.company_id,
                date
            )
            actual = company_currency._convert(
                inv.amount_total if inv.payment_state == 'paid' else 0,
                target_currency,
                inv.company_id,
                date
            )
            sp['billing'] += actual
            cust['total_billing'] += actual

            if q:
                sp['quarters_projected'][q] += projected
                sp['quarters_actual'][q] += actual

                cust['quarters_projected'][q] += projected
                cust['quarters_actual'][q] += actual

        result = []
        for cust_name, cust_data in customers.items():

            salespersons = []
            for sp in cust_data['salespersons'].values():
                sp['products'] = ', '.join(sp['products'])
                salespersons.append(sp)

            result.append({
                'customer': cust_name,
                'country': cust_data['country'],
                'salespersons': salespersons,
                'total_booking': 0,
                'total_billing': cust_data['total_billing'],
                'quarters_projected': cust_data['quarters_projected'],
                'quarters_actual': cust_data['quarters_actual'],
            })

        expenses_data = {
            'people': 0,
            'tools': 0,
            'travel': 0,
            'misc': 0
        }

        expenses = self.env['hr.expense'].search([
            ('state', 'in', ['done', 'approved', 'post', 'posted'])
        ])

        for exp in expenses:
            name = (exp.name or '').lower()

            if any(x in name for x in ['salary', 'employee', 'wage']):
                expenses_data['people'] += exp.total_amount
            elif any(x in name for x in ['tool', 'software', 'license']):
                expenses_data['tools'] += exp.total_amount
            elif 'travel' in name:
                expenses_data['travel'] += exp.total_amount
            else:
                expenses_data['misc'] += exp.total_amount

        currency = self.env.company.currency_id

        return {
            'customers': result,
            'expenses': expenses_data,
            'quarters': ['q1', 'q2', 'q3', 'q4'],
            'currency': {
                'name': currency.name,
                'symbol': currency.symbol,
            }
        }

# class CustomPLLine(models.Model):
#     _name = 'custom.pl.line'

#     report_id = fields.Many2one('custom.pl.report')
#     partner_id = fields.Many2one('res.partner', string="Customer")

#     country_id = fields.Many2one(related='partner_id.country_id', store=True)

#     work_order = fields.Char()
#     tenure = fields.Integer()

#     financial_year = fields.Selection([
#         ('2025', '2025-2026'),
#         ('2026', '2026-2027'),
#     ])

    # quarter = fields.Selection([
    #     ('q1', 'Q1'),
    #     ('q2', 'Q2'),
    #     ('q3', 'Q3'),
    #     ('q4', 'Q4'),
    # ])

    # ================= XLSX EXPORT =================
    # @api.model
    # def action_download_xlsx(self, financial_year=None, quarters=None):

    #     data = self.get_filtered_data(financial_year, quarters)['data']

    #     output = io.BytesIO()
    #     workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    #     sheet = workbook.add_worksheet('P&L Report')

    #     # Formats
    #     bold = workbook.add_format({'bold': True, 'border': 1})
    #     normal = workbook.add_format({'border': 1})
    #     header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#0b3c4c', 'color': 'white'})
    #     yellow = workbook.add_format({'border': 1, 'bg_color': '#ffe600'})
    #     green = workbook.add_format({'border': 1, 'bg_color': '#7bdcb5', 'bold': True})

    #     row = 0

    #     # Header
    #     headers = ['Client Partner', 'GEO', 'Customer', 'Workorder', 'Tenure', 'Value','Value1']
    #     for col, h in enumerate(headers):
    #         sheet.write(row, col, h, header)

    #     col_offset = len(headers)

    #     quarters_list = quarters or ['q1', 'q2', 'q3', 'q4']

    #     for q in quarters_list:
    #         sheet.write(row, col_offset, q.upper() + " REV", header)
    #         sheet.write(row, col_offset + 1, "EXP", header)
    #         sheet.write(row, col_offset + 2, "GP", header)
    #         sheet.write(row, col_offset + 3, "GM", header)
    #         col_offset += 4

    #     row += 1

    #     # Data
    #     for partner in data.values():
    #         for geo in partner['geo_map'].values():
    #             for customer in geo['customers'].values():

    #                 for wo in customer['workorders']:
    #                     col = 0
    #                     sheet.write(row, col, partner['partner'], normal); col += 1
    #                     sheet.write(row, col, geo['geo'], normal); col += 1
    #                     sheet.write(row, col, customer['customer'], normal); col += 1
    #                     sheet.write(row, col, wo['workorder'], normal); col += 1
    #                     sheet.write(row, col, wo['tenure'], normal); col += 1
    #                     sheet.write(row, col, wo['value'], normal); col += 1
    #                     sheet.write(row, col, wo['value'], normal); col += 1
                        
                        # for q in quarters_list:
                        #     qdata = customer['quarters'].get(q, {})
                        #     sheet.write(row, col, qdata.get('rev', 0), yellow); col += 1
                        #     sheet.write(row, col, qdata.get('exp', 0), yellow); col += 1
                        #     sheet.write(row, col, qdata.get('gp', 0), yellow); col += 1
                        #     sheet.write(row, col, qdata.get('gm', 0), yellow); col += 1

                        # row += 1

                # ✅ Portfolio row
    #             sheet.write(row, 0, 'Portfolio Total', green)
    #             sheet.write(row, 5, geo['total_value'], green)
    #             row += 1

    #     workbook.close()
    #     output.seek(0)

    #     file = base64.b64encode(output.read())

    #     attachment = self.env['ir.attachment'].create({
    #         'name': 'PL_Report.xlsx',
    #         'type': 'binary',
    #         'datas': file,
    #     })

    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/{attachment.id}?download=true',
    #         'target': 'self',
    #     }

    # # ================= PDF =================
    # def action_print_pdf(self):
    #     return self.env.ref(
    #         'bxi_accounting_report.pl_report_pdf_action'
    #     ).report_action(self)


# ================= LINE MODEL =================
