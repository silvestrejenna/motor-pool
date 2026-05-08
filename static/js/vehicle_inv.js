// static/js/vehicle_inv.js

function editRow(id) {
  const row = document.getElementById(`row-${id}`);
  if (!row) return;

  const nameCell = row.querySelector(".v-name");
  const plate = row.querySelector(".v-plate");
  const color = row.querySelector(".v-color");
  const type = row.querySelector(".v-type");
  const status = row.querySelector(".v-status");
  const mileage = row.querySelector(".v-mileage");

  // Transform text into inputs
  // We use .trim() to ensure no accidental whitespace is carried over
  nameCell.innerHTML = `<input type="text" id="edit-name-${id}" value="${nameCell.textContent.trim()}" style="width:100%">`;
  plate.innerHTML = `<input type="text" id="edit-plate-${id}" value="${plate.textContent.trim()}" style="width:80px">`;
  color.innerHTML = `<input type="text" id="edit-color-${id}" value="${color.textContent.trim()}" style="width:70px">`;
  type.innerHTML = `<input type="text" id="edit-type-${id}" value="${type.textContent.trim()}" style="width:80px">`;

  // Status handling
  const statusText = status.textContent.trim();
  status.parentElement.innerHTML = `<input type="text" id="edit-status-${id}" value="${statusText}" style="width:80px">`;

  // Mileage handling (remove " km" to get the number)
  const mileageValue = parseInt(mileage.innerText) || 0;
  mileage.innerHTML = `<input type="number" id="edit-mileage-${id}" value="${mileageValue}" style="width:70px">`;

  // Toggle Buttons
  row.querySelector(".btn-edit").style.display = "none";
  document.getElementById(`upd-${id}`).style.display = "inline-block";
  document.getElementById(`cancel-${id}`).style.display = "inline-block";
}

function updateRow(id) {
  // Create a hidden form and submit it to the Flask route
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `/update_vehicle/${id}`;

  // List of fields to collect from the inputs we created in editRow
  const fields = ["name", "plate", "color", "type", "status", "mileage"];

  fields.forEach((field) => {
    const inputElement = document.getElementById(`edit-${field}-${id}`);
    if (inputElement) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = field;
      input.value = inputElement.value;
      form.appendChild(input);
    }
  });

  document.body.appendChild(form);
  form.submit();
}

async function loadUserProfile() {
  const res = await fetch("/auth/user");
  if (!res.ok) {
    window.location.href = "/";
    return;
  }
  const user = await res.json();
  document.getElementById("profileName").textContent = user.full_name;
  document.getElementById("profileEmail").textContent = user.email;
}

loadUserProfile();

function toggleProfile() {
  document.getElementById("profileDropdown").classList.toggle("show");
}

async function logout() {
  await fetch("/logout", { method: "POST" });
  window.location.href = "/";
}

function cancelUpdate(id) {
  const row = document.getElementById(`row-${id}`);

  // 1. Hide the Update and Cancel buttons
  document.getElementById(`upd-${id}`).style.display = "none";
  document.getElementById(`cancel-${id}`).style.display = "none";

  // 2. Show the Edit and Delete buttons (or whatever was there)
  row.querySelector(".btn-edit").style.display = "inline-block";
  row.querySelector(".btn-delete").style.display = "inline-block";

  // 3. Turn inputs back into text
  // We assume your editRow turned text into inputs; this refreshes the page
  // to discard any changes the user typed, which is the safest "Cancel".
  location.reload();
}

function closeDrawer() {
  document.getElementById("addModal").style.display = "none";
}

const bell = document.getElementById("notifBell");
const dropdown = document.getElementById("notifDropdown");
const notifList = document.getElementById("notifList");
const notifBadge = document.getElementById("notifBadge");

bell.addEventListener("click", async () => {
  dropdown.classList.toggle("hidden");

  if (!dropdown.classList.contains("hidden")) {
    await loadNotifications();
  }
});

async function loadUnreadCount() {
  try {
    const res = await fetch("/get_unread_notif_count");
    const data = await res.json();

    const badge = document.getElementById("notifBadge");

    console.log("Unread count:", data.count);

    if (data.count > 0) {
      badge.textContent = data.count;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  } catch (err) {
    console.error("Error loading unread count:", err);
  }
}

async function loadNotifications() {
  try {
    const res = await fetch("/get_notifications");
    const data = await res.json();
    notifList.innerHTML = "";

    if (data.length === 0) {
      notifList.innerHTML = "<p>No notifications</p>";
      return;
    }

    data.forEach((notif) => {
      const div = document.createElement("div");
      div.className = "notif-item";
      div.textContent = notif.message;
      div.style.cursor = "pointer";
      div.style.pointerEvents = "auto";

      if (!notif.is_read) {
        div.style.fontWeight = "bold";
      }

      div.onclick = async function () {
        console.log("CLICKED NOTIF:", notif.id);

        div.onclick = function () {
          console.log("CLICK WORKING");
        };

        try {
          const res = await fetch(`/mark_notification_read/${notif.id}`);
          const result = await res.json();

          await loadUnreadCount();
          window.location.href = result.redirect_url;
        } catch (err) {
          console.error("Error marking as read:", err);
        }
      };

      notifList.appendChild(div);
    });
  } catch (err) {
    console.error("Error loading notifications:", err);
    notifList.innerHTML = "<p>Failed to load notifications</p>";
  }
}
window.addEventListener("load", loadUnreadCount);

// ================= TAB SWITCH =================

function switchTab(tab) {
  const vehicleTable = document.getElementById("vehicle-content");
  const rfidTable = document.getElementById("rfid-table");

  const vehicleBtn = document.getElementById("vehicle-btn");
  const rfidBtn = document.getElementById("rfid-btn");

  const addBtn = document.getElementById("main-add-btn");

  if (!vehicleTable || !rfidTable) return;

  if (tab === "vehicle") {
    vehicleTable.style.display = "block";
    rfidTable.style.display = "none";

    if (vehicleBtn) vehicleBtn.classList.add("active");
    if (rfidBtn) rfidBtn.classList.remove("active");

    if (addBtn) {
      addBtn.innerText = "Add Vehicle Record";
      addBtn.onclick = toggleModal;
    }
  } else {
    vehicleTable.style.display = "none";
    rfidTable.style.display = "block";

    if (rfidBtn) rfidBtn.classList.add("active");
    if (vehicleBtn) vehicleBtn.classList.remove("active");

    if (addBtn) {
      addBtn.innerText = "Add RFID Record";
      addBtn.onclick = toggleRFIDModal;
    }
  }
}
// ================= RFID MODAL =================

function toggleRFIDModal() {
  const modal = document.getElementById("rfidModal");

  if (
    modal.style.display === "flex" ||
    getComputedStyle(modal).display === "flex"
  ) {
    modal.style.display = "none";
  } else {
    modal.style.display = "flex";
  }
}

// ================= RFID EDIT =================

function editRFIDRow(id) {
  const row = document.getElementById(`rfid-row-${id}`);

  // SAVE ORIGINAL VALUES
  const vehicle = row.querySelector(".r-vehicle").textContent.trim();
  const plate = row.querySelector(".r-plate").textContent.trim();

  const autoAcc = row.querySelector(".r-auto-acc").textContent.trim();
  const autoCard = row.querySelector(".r-auto-card").textContent.trim();

  const easyAcc = row.querySelector(".r-easy-acc").textContent.trim();
  const easyCard = row.querySelector(".r-easy-card").textContent.trim();

  // CONVERT TO INPUTS
  row.querySelector(".r-vehicle").innerHTML =
    `<input type="text" class="vehicle-input" value="${vehicle}">`;

  row.querySelector(".r-plate").innerHTML =
    `<input type="text" class="plate-input" value="${plate}">`;

  row.querySelector(".r-auto-acc").innerHTML =
    `<input type="text" class="auto-acc-input" value="${autoAcc}">`;

  row.querySelector(".r-auto-card").innerHTML =
    `<input type="text" class="auto-card-input" value="${autoCard}">`;

  row.querySelector(".r-easy-acc").innerHTML =
    `<input type="text" class="easy-acc-input" value="${easyAcc}">`;

  row.querySelector(".r-easy-card").innerHTML =
    `<input type="text" class="easy-card-input" value="${easyCard}">`;

  // BUTTON TOGGLE
  row.querySelector(".btn-edit").style.display = "none";

  document.getElementById(`rfid-upd-${id}`).style.display = "inline-block";
  document.getElementById(`rfid-cancel-${id}`).style.display = "inline-block";
}

// ================= RFID CANCEL =================

function cancelRFIDEdit(id) {
  const row = document.getElementById(`rfid-row-${id}`);

  // GET ORIGINAL VALUES
  const vehicle = row.querySelector(".vehicle-input").defaultValue;

  const plate = row.querySelector(".plate-input").defaultValue;

  const autoAcc = row.querySelector(".auto-acc-input").defaultValue;

  const autoCard = row.querySelector(".auto-card-input").defaultValue;

  const easyAcc = row.querySelector(".easy-acc-input").defaultValue;

  const easyCard = row.querySelector(".easy-card-input").defaultValue;

  // RESTORE TEXT
  row.querySelector(".r-vehicle").innerHTML = vehicle;

  row.querySelector(".r-plate").innerHTML = plate;

  row.querySelector(".r-auto-acc").innerHTML = autoAcc;

  row.querySelector(".r-auto-card").innerHTML = autoCard;

  row.querySelector(".r-easy-acc").innerHTML = easyAcc;

  row.querySelector(".r-easy-card").innerHTML = easyCard;

  // BUTTONS
  row.querySelector(".btn-edit").style.display = "inline-block";

  document.getElementById(`rfid-upd-${id}`).style.display = "none";

  document.getElementById(`rfid-cancel-${id}`).style.display = "none";
}

function updateRFIDRow(id) {
  const row = document.getElementById(`rfid-row-${id}`);

  const vehicle = row.querySelector(".vehicle-input").value;
  const plate = row.querySelector(".plate-input").value;

  const autoAcc = row.querySelector(".auto-acc-input").value;
  const autoCard = row.querySelector(".auto-card-input").value;

  const easyAcc = row.querySelector(".easy-acc-input").value;
  const easyCard = row.querySelector(".easy-card-input").value;

  fetch(`/update_rfid/${id}`, {
    method: "POST",

    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },

    body: new URLSearchParams({
      vehicle: vehicle,
      plate: plate,

      auto_acc: autoAcc,
      auto_card: autoCard,

      easy_acc: easyAcc,
      easy_card: easyCard,
    }),
  }).then((response) => {
    if (response.ok) {
      alert("RFID record updated!");
      location.reload();
    } else {
      alert("Update failed.");
    }
  });
}

function deleteRFIDRow(id) {
  const confirmDelete = confirm("Delete this RFID record?");

  if (confirmDelete) {
    window.location.href = `/delete_rfid/${id}`;
  }
}
