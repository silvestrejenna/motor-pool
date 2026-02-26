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

document.addEventListener("DOMContentLoaded",() => {
    const reportType = document.getElementById("reportType");
    const defaultFields = document.getElementById("defaultFields");
    const monthlyFields = document.getElementById("monthlyFields");
    const defaultInputs = document.querySelectorAll("#defaultFields select");
    const monthlyInputs = document.querySelectorAll("#monthlyFields input, #monthlyFields select");

    monthlyInputs.forEach(input => input.disabled = true);

    reportType.addEventListener("change", () => {
        if (reportType.value === "monthly_monitoring") {
            defaultFields.style.display = "none";
            monthlyFields.style.display = "flex";
            defaultInputs.forEach(input => input.disabled = true);
            monthlyInputs.forEach(input => input.disabled = false);
        } else {
            defaultFields.style.display = "flex";
            monthlyFields.style.display = "none";
            defaultInputs.forEach(input => input.disabled = false);
            monthlyInputs.forEach(input => input.disabled = true);
        }
    });
});