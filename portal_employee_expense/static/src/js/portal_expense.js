/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PortalExpense = publicWidget.Widget.extend({
    selector: '#expense_form',

    events: {
        'click #add_line_btn': '_addLine',
        'click .remove_line': '_removeLine',
        //  ADD THIS
        'change input[name="date[]"]': '_onDateChange',
    },

    start() {
        // Hide remove button for first row
        this.el.querySelector('.expense_line .remove_line').style.display = 'none';
        return this._super(...arguments);
    },

    _addLine(ev) {
        ev.preventDefault();

        const container = this.el.querySelector('#expense_lines_container');
        const firstRow = container.querySelector('.expense_line');
        const newRow = firstRow.cloneNode(true);

        // Clear inputs
        newRow.querySelectorAll('input').forEach(input => {
            input.value = '';
        });

        // Show remove button
        const removeBtn = newRow.querySelector('.remove_line');
        removeBtn.style.display = 'inline-block';

        container.appendChild(newRow);
    },

    _removeLine(ev) {
        ev.preventDefault();
        const row = ev.currentTarget.closest('.expense_line');
        if (row) {
            row.remove();
        }
    },
    //  NEW FUNCTION (for reimbursement_date auto-fill)
    _onDateChange(ev) {
        const input = ev.currentTarget;
        const value = input.value;

        if (!value) return;

        const date = new Date(value);

        let year = date.getFullYear();
        let month = date.getMonth() + 1;

        // next month logic
        if (month === 12) {
            month = 1;
            year += 1;
        } else {
            month += 1;
        }

        const reimbursementDate = new Date(year, month - 1, 15);
        const formatted = reimbursementDate.toISOString().split('T')[0];

        // set in same row
        const row = input.closest('.expense_line');
        row.querySelector('.reimbursement_date').value = formatted;
    }
});
