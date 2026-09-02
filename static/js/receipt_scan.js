document.addEventListener("DOMContentLoaded", function () {
    const scanBtn = document.getElementById("scanReceiptBtn");
    const fileInput = document.getElementById("receiptFile");
    const statusEl = document.getElementById("scanStatus");

    if (!scanBtn) return;

    scanBtn.addEventListener("click", async function () {
        const file = fileInput.files[0];
        if (!file) {
            statusEl.textContent = "Please choose a receipt image first.";
            statusEl.style.color = "#e63946";
            return;
        }

        const formData = new FormData();
        formData.append("receipt", file);

        scanBtn.disabled = true;
        scanBtn.textContent = "Scanning...";
        statusEl.textContent = "Reading your receipt...";
        statusEl.style.color = "#777";

        try {
            const response = await fetch("/expenses/scan-receipt", {
                method: "POST",
                body: formData
            });
            const data = await response.json();

            if (!response.ok) {
                statusEl.textContent = data.error || "Could not read receipt.";
                statusEl.style.color = "#e63946";
                return;
            }

            // Fill in whatever fields OCR managed to detect
            if (data.amount !== null && data.amount !== undefined) {
                document.getElementById("amount").value = data.amount;
            }
            if (data.date) {
                document.getElementById("date").value = data.date;
            }
            if (data.category) {
                const categorySelect = document.getElementById("category");
                const hasOption = [...categorySelect.options].some(o => o.value === data.category);
                if (hasOption) categorySelect.value = data.category;
            }
            if (data.description) {
                document.getElementById("description").value = data.description;
            }

            if (data.error) {
                // Partial read (e.g. amount not found) - fields are filled where possible
                statusEl.textContent = data.error;
                statusEl.style.color = "#e6a03e";
            } else {
                statusEl.textContent = "✅ Fields auto-filled — please review before saving.";
                statusEl.style.color = "#20c997";
            }
        } catch (err) {
            statusEl.textContent = "Something went wrong while scanning. Please try again.";
            statusEl.style.color = "#e63946";
        } finally {
            scanBtn.disabled = false;
            scanBtn.textContent = "Scan & Auto-fill";
        }
    });
});
