// odoo.define('portal_employee_expense.form', function (require) {
//     "use strict";
//
//     var publicWidget = require('web.public.widget');
//
//     publicWidget.registry.Form = publicWidget.Widget.extend({
//         selector: '#expense_table',
//
//         events: {
//             'click #add_line': '_addLine',
//         },
//
//         _addLine: function () {
//             var $row = this.$('tbody tr:first').clone();
//             $row.find('input').val('');
//             this.$('tbody').append($row);
//         },
//     });
// });