document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('expense_lines_container');
    var addBtn = document.getElementById('add_line_btn');

    addBtn.addEventListener('click', function () {
        // Clone the first row
        var firstRow = container.querySelector('.expense_line');
        var newRow = firstRow.cloneNode(true);

        // Clear input values
        newRow.querySelectorAll('input').forEach(function(input){
            if(input.type === 'file'){
                input.value = '';
            } else {
                input.value = '';
            }
        });

        // Show remove button
        var removeBtn = newRow.querySelector('.remove_line');
        removeBtn.style.display = 'inline-block';

        removeBtn.addEventListener('click', function(){
            newRow.remove();
        });

        // Append new row
        container.appendChild(newRow);
    });

    // Hide remove button on first row
    container.querySelector('.expense_line .remove_line').style.display = 'none';
});