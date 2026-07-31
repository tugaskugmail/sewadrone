// DroneRent - Main JavaScript

document.addEventListener('DOMContentLoaded', function () {
    // Tooltip initialization
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (el) {
        return new bootstrap.Tooltip(el);
    });

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function () {
        document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
            var bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) bsAlert.close();
        });
    }, 5000);

    // Price calculator on booking page
    const startDate = document.getElementById('start_date');
    const endDate = document.getElementById('end_date');
    const calcResult = document.getElementById('calc-result');

    if (startDate && endDate) {
        // Set minimum date to today
        const today = new Date().toISOString().split('T')[0];
        startDate.setAttribute('min', today);

        function updatePrice() {
            if (startDate.value && endDate.value) {
                const start = new Date(startDate.value);
                const end = new Date(endDate.value);
                if (end >= start) {
                    const days = Math.floor((end - start) / (1000 * 60 * 60 * 24)) + 1;
                    const rate = parseInt(document.getElementById('daily_rate').value);
                    const deposit = parseInt(document.getElementById('deposit').value);
                    const total = rate * days;

                    document.getElementById('total_days').value = days;
                    document.getElementById('total_price').value = total;

                    if (calcResult) {
                        calcResult.innerHTML = `
                            <div class="price-detail mt-3">
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Durasi</span>
                                    <span>${days} hari</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Rp ${rate.toLocaleString('id-ID')} × ${days} hari</span>
                                    <span>Rp ${total.toLocaleString('id-ID')}</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Deposit (dikembalikan)</span>
                                    <span>Rp ${deposit.toLocaleString('id-ID')}</span>
                                </div>
                                <hr class="border-secondary">
                                <div class="d-flex justify-content-between fw-bold">
                                    <span>Total + Deposit</span>
                                    <span class="text-primary">Rp ${(total + deposit).toLocaleString('id-ID')}</span>
                                </div>
                            </div>
                        `;
                    }
                }
            }
        }

        startDate.addEventListener('change', function () {
            endDate.setAttribute('min', startDate.value);
            updatePrice();
        });
        endDate.addEventListener('change', updatePrice);
    }

    // Confirm delete actions
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(el.getAttribute('data-confirm') || 'Yakin?')) {
                e.preventDefault();
            }
        });
    });
});
