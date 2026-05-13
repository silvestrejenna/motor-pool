function toggleFuelModal() {
  const modal = document.getElementById("fuelModal");
  modal.style.display = modal.style.display === "flex" ? "none" : "flex";
}

// Close modal if user clicks outside
window.onclick = function (event) {
  if (event.target.className === "modal-overlay") {
    event.target.style.display = "none";
  }
};

// Same logic as vehicle inventory, just different field names
function editFuel(id) {
  const row = document.getElementById(`row-${id}`);
  // Logic to transform cells to inputs...
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

//Auto calculate km used
// Dedicated calculation for the "Add Fuel" Modal
function calcAddKM() {
  // We use getElementById to ensure we are grabbing the Modal inputs specifically
  const start = parseFloat(document.getElementById("add_km_start").value) || 0;
  const end = parseFloat(document.getElementById("add_km_end").value) || 0;
  const usedField = document.getElementById("add_km_used");

  if (end >= start) {
    usedField.value = end - start;
  } else {
    usedField.value = 0; // Prevents negative numbers
  }
}

function toggleEdit(id) {
  const row = document.getElementById(`row-${id}`);
  const viewModes = row.querySelectorAll(".view-mode");
  const editModes = row.querySelectorAll(".edit-mode");
  const viewBtns = row.querySelector(`.view-btns-${id}`);
  const editBtns = row.querySelector(`.edit-btns-${id}`);

  const isEditing = editModes[0].style.display === "block";

  if (isEditing) {
    // Switch to View Mode
    viewModes.forEach((el) => (el.style.display = "inline"));
    editModes.forEach((el) => (el.style.display = "none"));
    viewBtns.style.display = "block";
    editBtns.style.display = "none";
  } else {
    // Switch to Edit Mode
    viewModes.forEach((el) => (el.style.display = "none"));
    editModes.forEach((el) => (el.style.display = "block"));
    viewBtns.style.display = "none";
    editBtns.style.display = "flex"; // Use flex for better button alignment
  }
}

// KM calculation inside the row while editing
document.querySelectorAll("tr").forEach((row) => {
  const kmStart = row.querySelector('input[name="km_beginning"]');
  const kmEnd = row.querySelector('input[name="km_end"]');
  const kmUsed = row.querySelector('input[name="km_used"]');

  if (kmStart && kmEnd) {
    [kmStart, kmEnd].forEach((input) => {
      input.addEventListener("input", () => {
        const start = parseFloat(kmStart.value) || 0;
        const end = parseFloat(kmEnd.value) || 0;
        kmUsed.value = end >= start ? end - start : 0;
      });
    });
  }
});

function deleteFuel(id) {
  if (confirm("Are you sure you want to delete this record?")) {
    window.location.href = `/delete_fuel/${id}`;
  }
}

function saveUpdate(id) {
  const row = document.getElementById(`row-${id}`);
  const inputs = row.querySelectorAll(".edit-input");

  // Create an object to hold the data
  const data = { id: id };
  inputs.forEach((input) => {
    data[input.name] = input.value;
  });

  // Send data to Flask via Fetch API
  fetch("/update_fuel", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => {
      if (response.ok) {
        alert("Record updated successfully!");
        location.reload(); // Reload to show the updated data
      } else {
        alert("Failed to update record.");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while saving.");
    });
}

function closeDrawer() {
  document.getElementById("fuelModal").style.display = "none";
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
window.onload = loadUnreadCount;
