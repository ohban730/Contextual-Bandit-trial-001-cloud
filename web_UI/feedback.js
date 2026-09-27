const feedbackUrl = CONFIG.FEEDBACK_URL;

async function sendFeedback(label, suggestionId) {

    if (!suggestionId) {
        throw new Error('評価する提案がありません');
    }
    
    const requestUrl = new URL(feedbackUrl);
    requestUrl.searchParams.set('label', label);
    requestUrl.searchParams.set('suggestion_id', suggestionId);

    const resp = await fetch(requestUrl, { method: 'POST' });

    if (!resp.ok) {
        throw new Error(`評価の送信に失敗しました（status: ${resp.status}）`);
    }
    const json = await resp.json();
    return json;
}