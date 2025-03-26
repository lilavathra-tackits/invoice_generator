
// {% comment %} calls update and add row  {% endcomment %}
// document.addEventListener('DOMContentLoaded', function() {
//     const tableBody = document.getElementById('item-table');
//     if (!tableBody.querySelector('tr')) {
//         console.log("No rows found on load, adding a default row.");
//         addDefaultRow();
//     } else {
//         updateAllRows();
//     }
// });

//{% comment %} Add default row in create invoice {% endcomment %}
function addDefaultRow() {
    const tableBody = document.getElementById('item-table');
    const totalForms = document.querySelector('#id_items-TOTAL_FORMS');
    const formIdx = parseInt(totalForms.value) || 0;
    const newRow = document.createElement('tr');
    newRow.className = 'item-row';
    newRow.innerHTML = `
        <td><select name="items-${formIdx}-product" id="id_items-${formIdx}-product" class="form-select"><option value="">Select Product</option></select></td>
        <td><input type="number" name="items-${formIdx}-quantity" id="id_items-${formIdx}-quantity" class="form-control" value="0" min="0"></td>
        <td><select name="items-${formIdx}-unit" id="id_items-${formIdx}-unit" class="form-select"><option value="">Select Unit</option></select></td>
        <td class="rate">0.00</td>
        <td><input type="number" name="items-${formIdx}-discount" id="id_items-${formIdx}-discount" class="form-control" value="0" min="0" max="100" step="0.01"></td>
        <td class="amount">0.00</td>
        <td><button type="button" class="btn btn-danger btn-sm" onclick="removeItemRow(this)">-</button></td>
    `;
    tableBody.appendChild(newRow);
    totalForms.value = formIdx + 1;
    updateRow(newRow);
}

function addItemRow() {
    console.log("addItemRow called manually via + button, adding new row");
    const tableBody = document.getElementById('item-table');
    const totalForms = document.querySelector('#id_items-TOTAL_FORMS');
    if (!totalForms) {
        console.error("Total forms element not found!");
        return;
    }
    const formIdx = parseInt(totalForms.value);
    const firstRow = tableBody.querySelector('tr');
    
    if (!firstRow) {
        console.log("No rows found to clone, adding a default row.");
        addDefaultRow();
        return; 
    }

    const newRow = firstRow.cloneNode(true);
    newRow.querySelectorAll('[name]').forEach(input => {
        const name = input.name.replace(/-\d+-/, `-${formIdx}-`);
        input.name = name;
        const id = input.id.replace(/-\d+-/, `-${formIdx}-`);
        input.id = id;
        if (input.name.includes('id')) {
            input.value = '';
        }
        if (input.type === 'select-one') {
            input.value = '';
        } else if (input.type === 'number') {
            input.value = '0';
        }
    });

    newRow.querySelector('.rate').textContent = '0.00';
    newRow.querySelector('.amount').textContent = '0.00';
    newRow.querySelector('td:last-child').innerHTML = '<button type="button" class="btn btn-danger btn-sm" onclick="removeItemRow(this)">-</button>';
    tableBody.appendChild(newRow);
    totalForms.value = formIdx + 1;
    updateRow(newRow);
}

//{% comment %} Remove and reindex rows {% endcomment %}
function removeItemRow(button) {
    console.log("removeItemRow called, removing row");
    const row = button.closest('tr');
    const totalFormsInput = document.querySelector('#id_items-TOTAL_FORMS');
    const rows = document.querySelectorAll('#item-table tr');

    if (rows.length <= 1) {
        console.log("Cannot remove the last row.");
        alert("At least one item is required.");
        return;
    }

    // Check if this row has an id (existing InvoiceItem)
    const idInput = row.querySelector('input[name$="-id"]');
    if (idInput && idInput.value) {
        // Existing row: mark it for deletion
        const deleteInput = row.querySelector('input[name$="-DELETE"]') || document.createElement('input');
        deleteInput.type = 'hidden';
        deleteInput.name = idInput.name.replace('-id', '-DELETE');
        deleteInput.value = 'on';
        row.appendChild(deleteInput);
        row.style.display = 'none'; // Hide instead of remove
    } else {
        // New row: remove it entirely and update TOTAL_FORMS
        row.remove();
        totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
    }

    reindexRows();

    updateTotals();
}

function reindexRows() {
    const rows = document.querySelectorAll('#item-table tr:not([style*="display: none"])');
    rows.forEach((row, index) => {
        row.querySelectorAll('[name]').forEach(input => {
            const oldName = input.name;
            const newName = oldName.replace(/-\d+-/, `-${index}-`);
            input.name = newName;
            const oldId = input.id;
            const newId = oldId.replace(/-\d+-/, `-${index}-`);
            input.id = newId;
        });
    });
}

//{% comment %} Update main functions {% endcomment %}
function updateRow(row) {
    console.log("updateRow called for row");
    const productSelect = row.querySelector('select[name$="product"]');
    const quantityInput = row.querySelector('input[name$="quantity"]');
    const discountInput = row.querySelector('input[name$="discount"]');
    const rateCell = row.querySelector('.rate');
    const amountCell = row.querySelector('.amount');

    if (!productSelect || !quantityInput || !discountInput || !rateCell || !amountCell) {
        console.error("One or more elements not found in row:", { productSelect, quantityInput, discountInput, rateCell, amountCell });
        return;
    }

    const handleProductChange = function() {
        console.log("Product changed, fetching rate for product ID:", this.value);
        const productId = this.value;
        if (productId) {
            fetch(`/get-product-rate/${productId}/`)
                .then(response => response.json())
                .then(data => {
                    rateCell.textContent = parseFloat(data.rate).toFixed(2);
                    calculateAmount(row);
                })
                .catch(error => {
                    console.error('Error fetching rate:', error);
                    rateCell.textContent = '0.00';
                    calculateAmount(row);
                });
        } else {
            rateCell.textContent = '0.00';
            calculateAmount(row);
        }
    };

    productSelect.removeEventListener('change', handleProductChange);
    productSelect.addEventListener('change', handleProductChange);

    const handleInputChange = () => calculateAmount(row);
    quantityInput.removeEventListener('input', handleInputChange);
    discountInput.removeEventListener('input', handleInputChange);
    quantityInput.addEventListener('input', handleInputChange);
    discountInput.addEventListener('input', handleInputChange);

    if (productSelect.value) {
        handleProductChange.call(productSelect);
    }
}

//{% comment %} Calculate amount {% endcomment %}
function calculateAmount(row) {
    const quantity = parseFloat(row.querySelector('input[name$="quantity"]').value) || 0;
    const rate = parseFloat(row.querySelector('.rate').textContent) || 0;
    const discount = parseFloat(row.querySelector('input[name$="discount"]').value) || 0;
    const amount = quantity * rate * (1 - discount / 100);
    row.querySelector('.amount').textContent = amount.toFixed(2);
    updateTotals();
}

//{% comment %} Calculate Totals {% endcomment %}
function updateTotals() {
    const rows = document.querySelectorAll('#item-table tr');
    let totalQuantity = 0;
    let totalPrice = 0;
    rows.forEach(row => {
        totalQuantity += parseFloat(row.querySelector('input[name$="quantity"]').value) || 0;
        totalPrice += parseFloat(row.querySelector('.amount').textContent) || 0;
    });
    document.getElementById('total-quantity').textContent = totalQuantity.toFixed(2);
    document.getElementById('total-price').textContent = totalPrice.toFixed(2);
}

//{% comment %} Update all rows   {% endcomment %}
function updateAllRows() {
    //console.log("updateAllRows called, initializing existing rows only. Number of rows:", document.querySelectorAll('#item-table tr').length);
    document.querySelectorAll('#item-table tr').forEach(row => updateRow(row));
}

//{% comment %} Form validation {% endcomment %}
function validateForm() {
    const rows = document.querySelectorAll('#item-table tr');
    let isValid = true;
    rows.forEach(row => {
        const productSelect = row.querySelector('select[name$="product"]');
        const quantityInput = row.querySelector('input[name$="quantity"]');
        if (!productSelect.value) {
            alert('Please select a product for all rows.');
            isValid = false;
        }
        if (!quantityInput.value || parseFloat(quantityInput.value) <= 0) {
            alert('Please enter a valid quantity for all rows.');
            isValid = false;
        }
    });
    return isValid; 
}

//{% comment %} Exit and cancel buttons {% endcomment %}
function setAction(action) {
    document.getElementById('form-action').value = action;

    // Flag to skip validation
    const skipValidation = action === 'exit' || action === 'cancel';

    if (action === 'exit') {
        window.location.assign('/invoices');
        return false;
    }

    if (action === 'cancel') {
        const redirectUrl = document.referrer || '/';
        window.location.assign(redirectUrl);
        return false;
    }

    if (!skipValidation) {
        return validateForm();
    }
    return true; // Shouldn't reach here, but added for safety
}
