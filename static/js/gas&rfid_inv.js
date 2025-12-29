function toggleFuelModal() {
    const modal = document.getElementById('fuelModal');
    modal.style.display = (modal.style.display === 'flex') ? 'none' : 'flex';
}

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
document.addEventListener('DOMContentLoaded', function() {
    const kmStart = document.querySelector('input[name="km_beginning"]');
    const kmEnd = document.querySelector('input[name="km_end"]');
    const kmUsed = document.querySelector('input[name="km_used"]');

    function calculateKM() {
        const start = parseFloat(kmStart.value) || 0;
        const end = parseFloat(kmEnd.value) || 0;
        
        if (end >= start) {
            kmUsed.value = end - start;
        } else {
            kmUsed.value = 0;
        }
    }

    kmStart.addEventListener('input', calculateKM);
    kmEnd.addEventListener('input', calculateKM);
});