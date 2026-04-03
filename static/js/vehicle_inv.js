// static/js/vehicle_inv.js

function toggleModal() {
  const modal = document.getElementById("addModal");
  modal.style.display = modal.style.display === "flex" ? "none" : "flex";
}

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
  window.onload = loadUnreadCount;
}
