// === 要素の取得 ---
const chipList = document.querySelector('#chip-list');
const sendButton = document.querySelector('#send-button');
const messages = document.querySelector('#messages');

// --- メッセージを１つ追加 ---
function addMessage(text, sender) {
    const bubble = document.createElement('div');

    bubble.classList.add('message', sender);
    bubble.textContent = text;
    messages.append(bubble);
    bubble.scrollIntoView({ block: 'end'});
}

// --- チップのクリック：選択の切り替えだけ ---
chipList.addEventListener('click', (event) => {
    const clickedChip = event.target.closest('.chip');

    if (!clickedChip) return;

    chipList.querySelectorAll('.chip').forEach((chip) => {
        chip.classList.remove('selected');
    });
    clickedChip.classList.add('selected');
});

// --- ↑ボタンのクリック：会話を進める ---
sendButton.addEventListener('click', () => {
    const selectedChip = chipList.querySelector('.chip.selected');
    const label = selectedChip.textContent;

    document.body.classList.add('chatting');
    addMessage(label, 'user');
});