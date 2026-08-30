// trends.js - Full logic for Expense Trends page (no inline data injection)

let categoryChart = null;

document.addEventListener('DOMContentLoaded', function () {
    const canvas = document.getElementById('categoryTrendChart');
    if (!canvas) return;

    const initialCategory = canvas.dataset.category || 'Food';
    loadCategoryTrend(initialCategory);

    const select = document.getElementById('category-select');
    if (select) {
        select.addEventListener('change', function () {
            loadCategoryTrend(select.value);
        });
    }
});

function loadCategoryTrend(category) {
    fetch(`/api/trends/category-data?category=${encodeURIComponent(category)}`)
        .then((res) => {
            if (!res.ok) throw new Error(`Request failed: ${res.status}`);
            return res.json();
        })
        .then((data) => renderCategoryTrendChart(data.labels, data.data))
        .catch((err) => {
            console.error('Failed to load trend data:', err);
            const canvas = document.getElementById('categoryTrendChart');
            if (canvas) renderEmptyState(canvas, 'Could not load trend data.');
        });
}

const lastValueLabelPlugin = {
    id: 'lastValueLabel',
    afterDatasetsDraw(chart) {
        const meta = chart.getDatasetMeta(0);
        const lastPoint = meta.data[meta.data.length - 1];
        if (!lastPoint) return;

        const dataArr = chart.data.datasets[0].data;
        const value = dataArr[dataArr.length - 1];
        const label = `₹${Number(value).toLocaleString('en-IN')}`;

        const { ctx } = chart;
        const x = lastPoint.x;
        const y = lastPoint.y - 18;

        ctx.save();
        ctx.font = 'bold 13px sans-serif';
        const textWidth = ctx.measureText(label).width;
        const paddingX = 8, boxHeight = 22;
        const boxWidth = textWidth + paddingX * 2;

        ctx.fillStyle = '#e03131';
        roundRect(ctx, x - boxWidth / 2, y - boxHeight - 6, boxWidth, boxHeight, 6);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x, y - boxHeight / 2 - 6 + 1);
        ctx.restore();
    }
};

function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
}

function renderCategoryTrendChart(labels, data) {
    const canvas = document.getElementById('categoryTrendChart');
    if (!canvas) return;

    // Reset canvas each time (clears any previous empty-state message)
    canvas.style.display = '';
    const existingMsg = canvas.parentElement.querySelector('.empty-state');
    if (existingMsg) existingMsg.remove();

    if (!labels.length || !data.length) {
        renderEmptyState(canvas, 'No trend data available for this category');
        return;
    }

    if (categoryChart) {
        categoryChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 300);
    gradient.addColorStop(0, 'rgba(224, 49, 49, 0.25)');
    gradient.addColorStop(1, 'rgba(224, 49, 49, 0.02)');

    categoryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Total Amount (₹)',
                    data: data,
                    borderColor: '#e03131',
                    backgroundColor: gradient,
                    borderWidth: 3,
                    pointRadius: (context) => (context.dataIndex === data.length - 1 ? 6 : 3),
                    pointBackgroundColor: '#e03131',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    tension: 0.35,
                    fill: true
                }
            ]
        },
        plugins: [lastValueLabelPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 40 } },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => `₹${Number(context.parsed.y).toLocaleString('en-IN')}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#f0f0f0' },
                    ticks: { callback: (value) => '₹' + Number(value).toLocaleString('en-IN') }
                },
                x: {
                    grid: { display: false },
                    ticks: { autoSkip: true, maxRotation: 45, minRotation: 0 }
                }
            }
        }
    });
}

function renderEmptyState(canvas, message) {
    canvas.style.display = 'none';
    const msg = document.createElement('div');
    msg.className = 'empty-state';
    msg.innerHTML = `<p>${message}</p>`;
    canvas.parentElement.appendChild(msg);
}