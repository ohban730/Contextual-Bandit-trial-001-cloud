// --- 設定と状態 ---
const CHIP_SETS = {
    category: [
        { label: 'すべて', value: '' },
        { label: '音楽', value: 'Music' },
        { label: 'ゲーム', value: 'Gaming' },
    ],
    feedback: [
        { label: 'GOOD', value: 'good' },
        { label: 'BAD', value: 'bad' },
    ],
};
let mode = 'category';
let currentSuggestionId = null;  // 表示中の提案。feedbackはこのIDに対して送る

// --- 要素の取得 ---
const chipList = document.querySelector('#chip-list');
const sendButton = document.querySelector('#send-button');
const messages = document.querySelector('#messages');

// --- チップを作り直す ---
function renderChips(newMode) {
    mode = newMode;
    chipList.replaceChildren();
    CHIP_SETS[newMode].forEach((item) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('chip');
        button.textContent = item.label;
        button.dataset.value = item.value;
        chipList.append(button);
    });
    chipList.firstElementChild.classList.add('selected');
}

// --- メッセージを１つ追加 ---
function addMessage(text, sender) {
    const bubble = document.createElement('div');

    bubble.classList.add('message', sender);
    bubble.textContent = text;
    messages.append(bubble);
    bubble.scrollIntoView({ block: 'end', behavior: 'smooth' });
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
sendButton.addEventListener('click', async () => {
    const selectedChip = chipList.querySelector('.chip.selected');
    const text = selectedChip.textContent;
    const value = selectedChip.dataset.value;

    document.body.classList.add('chatting');
    addMessage(text, 'user');

    setBusy(true);
    try {
        if (mode === 'category') {
            await requestSuggestion(value);
        } else {
            await requestFeedback(value);
        }
    } finally {
        setBusy(false);
    }
});

// --- 提案をもらう ---
async function requestSuggestion(category) {
    try {
        const json = await fetchSuggestion(category);
        currentSuggestionId = json.suggestion_id;
        addMessage(json.last_video_title, 'bot');
        renderChips('feedback');
    } catch (error) {
        console.error(error);
        addMessage(error.userMessage ?? '提案を取得できませんでした。もう一度お試しください。', 'bot');
    }
}

// --- 評価を送る ---
async function requestFeedback(label) {
    try {
        const json = await sendFeedback(label, currentSuggestionId);
        addMessage(`${json.channel_name} に ${json.label.toUpperCase()} 評価を送信しました`, 'bot');
        currentSuggestionId = null;
        renderChips('category');
    } catch (error) {
        console.error(error);
        addMessage(error.userMessage ?? '評価の送信に失敗しました。もう一度お試しください。', 'bot');
    }
}

// --- 待機中の切り替え ---
function setBusy(isBusy) {
    sendButton.disabled = isBusy;
    chipList.querySelectorAll('.chip').forEach((chip) => {
        chip.disabled = isBusy;
    });
}