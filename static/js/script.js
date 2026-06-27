/* static/js/script.js */
document.addEventListener('DOMContentLoaded', function () {
    // Автоскрытие flash-сообщений через 5 сек
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                alert.style.display = 'none';
            }
        }, 5000);
    });

    // Кликабельные артикулы → Google
    document.addEventListener('click', function (e) {
        var link = e.target.closest('.article-link');
        if (link) {
            e.preventDefault();
            var article = link.getAttribute('data-article');
            if (article) {
                window.open('https://www.google.com/search?q=' + encodeURIComponent(article), '_blank');
            }
        }
    });

    // Confirm delete
    document.addEventListener('submit', function (e) {
        if (e.target.classList.contains('confirm-delete')) {
            if (!confirm('Удалить заказ? Это действие необратимо.')) {
                e.preventDefault();
            }
        }
    });
});
