function toggleMainModal() {
  const modal = document.getElementById("m-modal");

  if (getComputedStyle(modal).display === "none") {
    modal.style.display = "flex";
  } else {
    modal.style.display = "none";
  }
}

function togglePMSModal() {
  const modal = document.getElementById("p-modal");

  if (getComputedStyle(modal).display === "none") {
    modal.style.display = "flex";
  } else {
    modal.style.display = "none";
  }
}

function switchTab(tab) {
  const mSec = document.getElementById("maintenance-section");
  const pSec = document.getElementById("pms-section");
  const mBtn = document.getElementById("m-btn");
  const pBtn = document.getElementById("p-btn");

  if (tab === "maintenance") {
    mSec.style.display = "block";
    pSec.style.display = "none";
    mBtn.classList.add("active");
    pBtn.classList.remove("active");
  } else {
    mSec.style.display = "none";
    pSec.style.display = "block";
    pBtn.classList.add("active");
    mBtn.classList.remove("active");
  }
}

function openModal(id) {
  document.getElementById(id).style.display = "block";
}

function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

// Close modal if user clicks outside
window.onclick = function (event) {
  if (event.target.className === "modal") {
    event.target.style.display = "none";
  }
};

// User Profile Management
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

function editMRow(id) {
  const row = document.getElementById(`m-row-${id}`);
  if (!row) return;

  const date = row.querySelector(".m-date");
  const vehicle = row.querySelector(".m-vehicle");
  const problem = row.querySelector(".m-problem");
  const action = row.querySelector(".m-action_taken");
  const cost = row.querySelector(".m-cost");
  const mechanic = row.querySelector(".m-mechanic");

  date.innerHTML = `<input type="date" id="m-date-${id}" value="${date.innerText.trim()}">`;

  vehicle.innerHTML = `<input type="text" id="m-vehicle-${id}" value="${vehicle.innerText.trim()}">`;

  problem.innerHTML = `<input type="text" id="m-problem-${id}" value="${problem.innerText.trim()}">`;

  action.innerHTML = `<input type="text" id="m-action_taken-${id}" value="${action.innerText.trim()}">`;

  const cleanCost = cost.innerText.replace("₱", "").trim();
  cost.innerHTML = `<input type="number" id="m-cost-${id}" value="${cleanCost}">`;

  mechanic.innerHTML = `<input type="text" id="m-mechanic-${id}" value="${mechanic.innerText.trim()}">`;

  // 🔴 UI STATE FIX
  row.querySelector(".btn-edit").style.display = "none";

  document.getElementById(`m-upd-${id}`).style.display = "inline-block";
  document.getElementById(`m-cancel-${id}`).style.display = "inline-block";
}

function updateMRow(id) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `/update_maintenance/${id}`;

  const fields = [
    "date",
    "vehicle",
    "problem",
    "action_taken",
    "cost",
    "mechanic",
  ];

  fields.forEach((field) => {
    const el = document.getElementById(`m-${field}-${id}`);
    if (el) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = field;
      input.value = el.value;
      form.appendChild(input);
    }
  });

  document.body.appendChild(form);
  form.submit();
}

function cancelMEdit(id) {
  location.reload();
}

// PMS Editing Functions
function editPMS(id) {
  const row = document.getElementById(`p-row-${id}`);
  if (!row) return;

  const vehicleCell = row.querySelector(".p-vehicle");
  const lastCell = row.querySelector(".p-last");
  const kmCell = row.querySelector(".p-km");
  const oilCell = row.querySelector(".p-oil");
  const nextCell = row.querySelector(".p-next");

  const lastDate = lastCell.dataset.date || "";
  const nextDate = nextCell.dataset.date || "";

  vehicleCell.innerHTML = `<input type="text" id="p-vehicle-${id}" value="${vehicleCell.innerText.trim()}">`;

  lastCell.innerHTML = `<input type="date" id="p-last_pms_date-${id}" value="${lastDate || ""}">`;

  const kmValue = kmCell.innerText.replace("km", "").trim();
  kmCell.innerHTML = `<input type="number" id="p-km-${id}" value="${kmValue}">`;

  const oilValue = oilCell.innerText.replace("L", "").trim();
  oilCell.innerHTML = `<input type="number" step="0.01" id="p-oil_liters-${id}" value="${oilValue}">`;

  nextCell.innerHTML = `<input type="date" id="p-next_pms_date-${id}" value="${nextDate || ""}">`;

  document.querySelector(`#p-row-${id} .btn-edit`).style.display = "none";
  document.getElementById(`p-upd-${id}`).style.display = "inline-block";
  document.getElementById(`p-cancel-${id}`).style.display = "inline-block";
}

function updatePMS(id) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `/update_pms/${id}`;

  const fields = [
    "vehicle",
    "last_pms_date",
    "km",
    "oil_liters",
    "next_pms_date",
  ];

  fields.forEach((field) => {
    const el = document.getElementById(`p-${field}-${id}`);
    if (el) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = field;
      input.value = el.value;
      form.appendChild(input);
    }
  });

  document.body.appendChild(form);
  form.submit();
}

function cancelPMS(id) {
  location.reload();
}
