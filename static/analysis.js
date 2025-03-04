// Sample data
const sampleData = [
    { date: '2025-02-24', detections: 5 },
    { date: '2025-02-25', detections: 8 },
    { date: '2025-02-26', detections: 3 },
    { date: '2025-03-01', detections: 10 },
    { date: '2025-03-05', detections: 7 },
  ];
  
  // Initial chart reference
  let chart;
  
  // Create the chart
  function createChart(filteredData) {
    const ctx = document.getElementById('chartCanvas').getContext('2d');
  
    // If the chart already exists, destroy it before creating a new one
    if (chart) {
      chart.destroy();
    }
  
    // Prepare the chart data
    const labels = filteredData.map(entry => entry.date);
    const data = filteredData.map(entry => entry.detections);
  
    // Create a new chart
    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Detections',
          data: data,
          borderColor: '#8884d8',
          fill: false,
          tension: 0.4, // Smooths the line
        }]
      },
      options: {
        responsive: true,
        plugins: {
          tooltip: {
            enabled: true,
          },
          legend: {
            display: true,
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Date'
            },
            type: 'category',
            labels: labels,
          },
          y: {
            title: {
              display: true,
              text: 'Detections'
            },
            min: 0,
          }
        }
      }
    });
  }
  
  // Filter data by date, month, or year
  function filterData() {
    const searchDate = document.getElementById('search-date').value;
    const searchMonth = document.getElementById('search-month').value;
    const searchYear = document.getElementById('search-year').value;
  
    const filteredData = sampleData.filter((entry) => {
      const entryDate = new Date(entry.date);
      const searchDateObj = searchDate ? new Date(searchDate) : null;
      const searchMonthObj = searchMonth ? new Date(searchMonth) : null;
      const searchYearValue = searchYear ? parseInt(searchYear, 10) : null;
  
      const matchesDate = searchDateObj
        ? entryDate.toDateString() === searchDateObj.toDateString()
        : true;
      const matchesMonth = searchMonthObj
        ? entryDate.getMonth() === searchMonthObj.getMonth() &&
          entryDate.getFullYear() === searchMonthObj.getFullYear()
        : true;
      const matchesYear = searchYearValue ? entryDate.getFullYear() === searchYearValue : true;
  
      return matchesDate && matchesMonth && matchesYear;
    });
  
    createChart(filteredData);
  }
  
  // Add event listeners to inputs
  document.getElementById('search-date').addEventListener('input', filterData);
  document.getElementById('search-month').addEventListener('input', filterData);
  document.getElementById('search-year').addEventListener('input', filterData);
  
  // Initial chart render with all data
  createChart(sampleData);
  