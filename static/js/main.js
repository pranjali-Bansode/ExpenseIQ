document.addEventListener("DOMContentLoaded", function () {

    const canvas = document.getElementById("expenseChart");

    if (!canvas) return;

    // Read data from HTML dataset
    const labels = JSON.parse(canvas.dataset.labels || "[]");
    const values = JSON.parse(canvas.dataset.values || "[]");

    const ctx = canvas.getContext("2d");

    new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Expenses (₹)",
                data: values,
                backgroundColor: "#00b386",
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

});


    function openBudgetModal(category, amount) {
    document.getElementById("budgetModal").style.display = "block";
    document.getElementById("category").value = category || "";
    document.getElementById("amount").value = amount || "";
}

    function closeBudgetModal() {
        document.getElementById("budgetModal").style.display = "none";
    }

    window.onclick = function(event) {
        var modal = document.getElementById("budgetModal");
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }
