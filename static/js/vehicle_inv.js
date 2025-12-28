// static/js/vehicle_inv.js

function toggleModal() {
    const modal = document.getElementById('addModal');
    modal.style.display = (modal.style.display === 'flex') ? 'none' : 'flex';
}

function editRow(id) {
    const row = document.getElementById(`row-${id}`);
    if (!row) return;

    const nameCell = row.querySelector('.v-name');
    const plate = row.querySelector('.v-plate');
    const color = row.querySelector('.v-color');
    const type = row.querySelector('.v-type');
    const status = row.querySelector('.v-status');
    const mileage = row.querySelector('.v-mileage');

    // Transform text into inputs
    // We use .trim() to ensure no accidental whitespace is carried over
    nameCell.innerHTML = `<input type="text" id="edit-name-${id}" value="${nameCell.innerText.trim()}" style="width:100px">`;
    plate.innerHTML = `<input type="text" id="edit-plate-${id}" value="${plate.innerText.trim()}" style="width:80px">`;
    color.innerHTML = `<input type="text" id="edit-color-${id}" value="${color.innerText.trim()}" style="width:70px">`;
    type.innerHTML = `<input type="text" id="edit-type-${id}" value="${type.innerText.trim()}" style="width:80px">`;
    
    // Status handling
    const statusText = status.innerText.trim();
    status.parentElement.innerHTML = `<input type="text" id="edit-status-${id}" value="${statusText}" style="width:80px">`;
    
    // Mileage handling (remove " km" to get the number)
    const mileageValue = parseInt(mileage.innerText) || 0;
    mileage.innerHTML = `<input type="number" id="edit-mileage-${id}" value="${mileageValue}" style="width:70px">`;

    // Toggle Buttons
    row.querySelector('.btn-edit').style.display = 'none';
    document.getElementById(`upd-${id}`).style.display = 'inline-block';
}

function updateRow(id) {
    // Create a hidden form and submit it to the Flask route
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/update_vehicle/${id}`;

    // List of fields to collect from the inputs we created in editRow
    const fields = ['name', 'plate', 'color', 'type', 'status', 'mileage'];
    
    fields.forEach(field => {
        const inputElement = document.getElementById(`edit-${field}-${id}`);
        if (inputElement) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = field;
            input.value = inputElement.value;
            form.appendChild(input);
        }
    });

    document.body.appendChild(form); 
    form.submit();
}