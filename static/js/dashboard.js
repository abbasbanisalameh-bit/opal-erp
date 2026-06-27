(function(){
    const incomeLabelsEl = document.getElementById("income-labels");
    const incomeValuesEl = document.getElementById("income-values");
    const incomeCanvas = document.getElementById("incomeChart");
    const attendanceCanvas = document.getElementById("attendanceChart");

    const labels = incomeLabelsEl ? JSON.parse(incomeLabelsEl.textContent || "[]") : [];
    const values = incomeValuesEl ? JSON.parse(incomeValuesEl.textContent || "[]") : [];

    const fallbackLabels = ["يناير","فبراير","مارس","أبريل","مايو","يونيو"];
    const fallbackValues = [0,0,0,0,0,0];

    if (incomeCanvas && window.Chart) {
        new Chart(incomeCanvas, {
            type: "bar",
            data: {
                labels: labels.length ? labels : fallbackLabels,
                datasets: [{
                    label: "الإيرادات (د.أ)",
                    data: values.length ? values : fallbackValues,
                    backgroundColor: "rgba(20,184,166,.9)",
                    borderRadius: 10,
                    maxBarThickness: 54
                }]
            },
            options: {
                responsive:true,
                maintainAspectRatio:false,
                plugins:{legend:{labels:{color:"#dbeafe"}}},
                scales:{
                    x:{ticks:{color:"#dbeafe"},grid:{color:"rgba(30,51,79,.7)"}},
                    y:{ticks:{color:"#dbeafe"},grid:{color:"rgba(30,51,79,.7)", beginAtZero:true}}
                }
            }
        });
    }

    if (attendanceCanvas && window.Chart) {
        const present = Number(attendanceCanvas.dataset.present || 0);
        const absent = Number(attendanceCanvas.dataset.absent || 0);
        new Chart(attendanceCanvas, {
            type: "doughnut",
            data: {
                labels: ["حاضر","غائب","متأخر","مستأذن"],
                datasets: [{
                    data: [present, absent, 0, 0],
                    backgroundColor: ["#22c55e","#ef4444","#f59e0b","#94a3b8"],
                    borderWidth: 0
                }]
            },
            options: {
                responsive:true,
                maintainAspectRatio:false,
                cutout:"62%",
                plugins:{legend:{display:false}}
            }
        });
    }
})();
