window.addEventListener('DOMContentLoaded', (event) => {
    const smsInput = document.getElementById('sms_text');
    const charsLeft = document.getElementById('chars_left');
    const maxLength = parseInt(smsInput.getAttribute('maxlength'));

    smsInput.addEventListener('input', function() {
        const remainingChars = calculateRemainingChars(smsInput.value);
        charsLeft.textContent = 'Characters left: ' + remainingChars;
    });

    function calculateRemainingChars(text) {
        const isUnicode = containsUnicodeChars(text);
        const maxChars = isUnicode ? 70 : 160;
        const remainingChars = maxChars - text.length;

        return Math.max(remainingChars, 0);
    }

    function containsUnicodeChars(text) {
        for (let i = 0; i < text.length; i++) {
            if (text.charCodeAt(i) > 127) {
                return true;
            }
        }
        return false;
    }
});
