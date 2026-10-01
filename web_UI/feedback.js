import { CONFIG } from './config.js';

const feedbackUrl = CONFIG.FEEDBACK_URL;

export async function sendFeedback(label, suggestionId) {

    if (!suggestionId) {
        throw new Error('評価する提案がありません');
    }
    
    const requestUrl = new URL(feedbackUrl);
    requestUrl.searchParams.set('label', label);
    requestUrl.searchParams.set('suggestion_id', suggestionId);

    const resp = await fetch(requestUrl, { method: 'POST' });

    if (!resp.ok) {
        const error = new Error(`評価の送信に失敗しました（status: ${resp.status}）`);

        try {
            const body = await resp.json();
            error.userMessage = body.error;
        } catch {
            // JSON でなければ、何もしない（userMessage なし → main.js で固定の文章を出す）
        }
        throw error;
    }

    const json = await resp.json();
    return json;
}