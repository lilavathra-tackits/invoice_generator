
//{% comment %} Edit {% endcomment %}
function editProduct(id, name, description, rate) {
    document.getElementById('product_id').value = id;
    document.getElementById('name').value = name;
    document.getElementById('description').value = description;
    document.getElementById('rate').value = rate;
}
//{% comment %} Clear {% endcomment %}
function clearForm() {
    document.getElementById('productForm').reset();
    document.getElementById('product_id').value = '';
}
