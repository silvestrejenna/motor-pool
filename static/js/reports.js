/*async function generateReport() {
    const monthSelect = document.getElementById("month");
    const yearSelect = document.getElementById("year");

    const month = monthSelect.value;
    const year = yearSelect.value;
    const monthName = monthSelect.options[monthSelect.selectedIndex].text;

    try {
        const response = await fetch("/generate-report", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                month: month,
                year: year,
                month_name: monthName
            })
        });

        if (!response.ok) {
            alert("Failed to generate report.");
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = `Gas_RFID_Report_${monthName}_${year}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

    } catch (error) {
        console.error(error);
        alert("An error occurred while generating the report.");
    }
}
    */

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

document.addEventListener("DOMContentLoaded", () => {
  const reportType = document.getElementById("reportType");
  const defaultFields = document.getElementById("defaultFields");
  const monthlyFields = document.getElementById("monthlyFields");
  const defaultInputs = document.querySelectorAll("#defaultFields select");
  const monthlyInputs = document.querySelectorAll(
    "#monthlyFields input, #monthlyFields select",
  );

  monthlyInputs.forEach((input) => (input.disabled = true));

  reportType.addEventListener("change", () => {
    if (reportType.value === "monthly_monitoring") {
      defaultFields.style.display = "none";
      monthlyFields.style.display = "flex";
      defaultInputs.forEach((input) => (input.disabled = true));
      monthlyInputs.forEach((input) => (input.disabled = false));
    } else {
      defaultFields.style.display = "flex";
      monthlyFields.style.display = "none";
      defaultInputs.forEach((input) => (input.disabled = false));
      monthlyInputs.forEach((input) => (input.disabled = true));
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const yearSelect = document.getElementById("reportYear");
  const currentYear = new Date().getFullYear();

  for (let year = currentYear + 1; year >= 2020; year--) {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = year;
    yearSelect.appendChild(option);
  }

  yearSelect.value = currentYear;
});
