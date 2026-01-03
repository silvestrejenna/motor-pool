function switchTab(tab) {
    const mSec = document.getElementById('maintenance-section');
    const pSec = document.getElementById('pms-section');
    const mBtn = document.getElementById('m-btn');
    const pBtn = document.getElementById('p-btn');

    if (tab === 'maintenance') {
        mSec.style.display = 'block';
        pSec.style.display = 'none';
        mBtn.classList.add('active');
        pBtn.classList.remove('active');
    } else {
        mSec.style.display = 'none';
        pSec.style.display = 'block';
        pBtn.classList.add('active');
        mBtn.classList.remove('active');
    }
}

function openModal(id) {
    document.getElementById(id).style.display = "block";
}

function closeModal(id) {
    document.getElementById(id).style.display = "none";
}

// Close modal if user clicks outside
window.onclick = function(event) {
    if (event.target.className === "modal") {
        event.target.style.display = "none";
    }
}

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