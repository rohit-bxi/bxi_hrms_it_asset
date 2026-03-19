/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PortalExpense = publicWidget.Widget.extend({
    selector: '#expense_form',

    events: {
        'click #add_line_btn': '_addLine',
        'click .remove_line': '_removeLine',
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
});